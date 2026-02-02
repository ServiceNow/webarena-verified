<?php

namespace App\Entity;

use App\CommentTree\CommentTree;
use App\Entity\Contracts\DomainEventsInterface as DomainEvents;
use App\Entity\Contracts\VisibilityInterface as Visibility;
use App\Entity\Contracts\Votable;
use App\Entity\Exception\BannedFromForumException;
use App\Entity\Exception\SubmissionLockedException;
use App\Entity\Traits\VisibilityTrait;
use App\Entity\Traits\VotableTrait;
use App\Event\CommentCreated;
use App\Event\CommentUpdated;
use Doctrine\Common\Collections\ArrayCollection;
use Doctrine\Common\Collections\Collection;
use Doctrine\Common\Collections\Criteria;
use Doctrine\Common\Collections\Selectable;
use Doctrine\ORM\Mapping as ORM;
use Symfony\Contracts\EventDispatcher\Event;

/**
 * @ORM\Entity(repositoryClass="App\Repository\CommentRepository")
 * @ORM\Table(indexes={
 *     @ORM\Index(name="comments_timestamp_id_idx", columns={"timestamp", "id"}),
 *     @ORM\Index(name="comments_timestamp_idx", columns={"timestamp"}),
 *     @ORM\Index(name="comments_search_idx", columns={"search_doc"}),
 *     @ORM\Index(name="comments_visibility_idx", columns={"visibility"}),
 * })
 */
class Comment implements DomainEvents, Visibility, Votable {
    use VisibilityTrait;
    use VotableTrait {
        getNetScore as private getRealNetScore;
    }

    public const MAX_BODY_LENGTH = 10000;

    /**
     * @ORM\Column(type="bigint")
     * @ORM\GeneratedValue(strategy="AUTO")
     * @ORM\Id()
     *
     * @var int|null
     */
    private $id;

    /**
     * @ORM\Column(type="text")
     *
     * @var string
     */
    private $body;

    /**
     * @ORM\Column(type="datetimetz_immutable")
     *
     * @var \DateTimeImmutable
     */
    private $timestamp;

    /**
     * @ORM\JoinColumn(nullable=false)
     * @ORM\ManyToOne(targetEntity="User", inversedBy="comments")
     *
     * @var User
     */
    private $user;

    /**
     * @ORM\JoinColumn(nullable=false)
     * @ORM\ManyToOne(targetEntity="Submission", inversedBy="comments")
     *
     * @var Submission
     */
    private $submission;

    /**
     * @ORM\ManyToOne(targetEntity="Comment", inversedBy="children")
     *
     * @var Comment|null
     */
    private $parent;

    /**
     * @ORM\OneToMany(targetEntity="Comment", mappedBy="parent", cascade={"remove"})
     *
     * @var Collection<array-key, Comment>&Selectable<array-key, Comment>
     */
    private $children;

    /**
     * @ORM\OneToMany(targetEntity="CommentVote", mappedBy="comment",
     *     fetch="EXTRA_LAZY", cascade={"persist"}, orphanRemoval=true)
     *
     * @var Collection<array-key, CommentVote>&Selectable<array-key, CommentVote>
     */
    private $votes;

    /**
     * @ORM\Column(type="text", options={"default": "visible"})
     *
     * @var string
     */
    private $visibility = self::VISIBILITY_VISIBLE;

    private ?\ArrayObject $cachedUserThreadVisibilityMap = null;

    /**
     * @ORM\Column(type="inet", nullable=true)
     *
     * @var string|null
     */
    private $ip;

    /**
     * @ORM\Column(type="datetimetz_immutable", nullable=true)
     *
     * @var \DateTimeImmutable|null
     */
    private $editedAt;

    /**
     * @ORM\Column(type="boolean", options={"default": false})
     *
     * @var bool
     */
    private $moderated = false;

    /**
     * @ORM\Column(type="text")
     *
     * @var string
     */
    private $userFlag = UserFlags::FLAG_NONE;

    /**
     * @ORM\OneToMany(targetEntity="CommentNotification", mappedBy="comment", cascade={"remove"}, orphanRemoval=true)
     *
     * @var Collection<array-key, CommentNotification>&Selectable<array-key, CommentNotification>
     */
    private $notifications;

    /**
     * @ORM\OneToMany(targetEntity="CommentMention", mappedBy="comment", cascade={"remove"}, orphanRemoval=true)
     *
     * @var Collection<array-key, CommentMention>&Selectable<array-key, CommentMention>
     */
    private $mentions;

    /**
     * @ORM\Column(type="integer")
     *
     * @var int
     */
    private $netScore = 0;

    /**
     * @ORM\Column(type="tsvector", nullable=true)
     */
    private $searchDoc;

    /**
     * @param Submission|Comment $parent
     */
    public function __construct(string $body, User $user, $parent, ?string $ip) {
        if ($ip !== null && !filter_var($ip, FILTER_VALIDATE_IP)) {
            throw new \InvalidArgumentException('Invalid IP address');
        }

        if ($parent instanceof Submission) {
            $submission = $parent;
            $parent = null;
        } elseif ($parent instanceof self) {
            $submission = $parent->getSubmission();
        } else {
            throw new \TypeError('$parent must be Submission or Comment');
        }

        if ($submission->isLocked() && !$user->isAdmin()) {
            throw new SubmissionLockedException();
        }

        if ($submission->getForum()->userIsBanned($user)) {
            throw new BannedFromForumException();
        }

        $this->body = $body;
        $this->user = $user;
        $this->submission = $submission;
        $this->parent = $parent;
        $this->ip = $user->isWhitelistedOrAdmin() ? null : $ip;
        $this->timestamp = new \DateTimeImmutable('@'.time());
        $this->children = new ArrayCollection();
        $this->votes = new ArrayCollection();
        $this->notifications = new ArrayCollection();
        $this->mentions = new ArrayCollection();
        $this->addVote($this->createVote(self::VOTE_UP, $user, $ip));
        $this->notify();

        if ($parent) {
            $parent->children->add($this);
        }

        $submission->addComment($this);
        $user->addComment($this);
    }

    public function getId(): ?int {
        return $this->id;
    }

    public function getBody(): string {
        return $this->body;
    }

    public function setBody(string $body): void {
        $this->body = $body;
    }

    public function getTimestamp(): \DateTimeImmutable {
        return $this->timestamp;
    }

    public function getUser(): User {
        return $this->user;
    }

    public function getSubmission(): Submission {
        return $this->submission;
    }

    public function getParent(): ?self {
        return $this->parent;
    }

    /**
     * Get replies, ordered by descending net score.
     *
     * @return Comment[]
     */
    public function getChildren(): array {
        $criteria = Criteria::create()->orderBy(['netScore' => 'DESC']);

        return $this->children->matching($criteria)->getValues();
    }

    /**
     * @return \Generator<Comment>
     */
    public function getChildrenRecursive(int &$startIndex = 0): \Generator {
        foreach ($this->getChildren() as $child) {
            // each yielded key must be unique, lol
            yield $startIndex++ => $child;
            yield from $child->getChildrenRecursive($startIndex);
        }
    }

    public function getReplyCount(): int {
        return \count($this->children);
    }

    public function removeReply(self $reply): void {
        $this->children->removeElement($reply);
    }

    /**
     * @return Collection<array-key, CommentVote>&Selectable<array-key, CommentVote>
     */
    protected function getVotes(): Collection {
        return $this->votes;
    }

    public function addMention(User $mentioned): void {
        if ($mentioned === $this->getUser()) {
            // don't notify yourself
            return;
        }

        if ($mentioned->isAccountDeleted()) {
            return;
        }

        if (!$mentioned->getNotifyOnMentions()) {
            // don't notify users who've disabled mention notifications
            return;
        }

        if ($mentioned->isBlocking($this->getUser())) {
            // don't notify users blocking you
            return;
        }

        $replyingTo = ($this->getParent() ?: $this->getSubmission())->getUser();

        if ($replyingTo === $mentioned && $replyingTo->getNotifyOnReply()) {
            // don't notify users who'll get a notification for the reply anyway
            return;
        }

        $mentioned->sendNotification(new CommentMention($mentioned, $this));
    }

    public function createVote(int $choice, User $user, ?string $ip): Vote {
        return new CommentVote($choice, $user, $ip, $this);
    }

    public function addVote(Vote $vote): void {
        if (!$vote instanceof CommentVote) {
            throw new \InvalidArgumentException(sprintf(
                '$vote must be of subtype %s, %s given',
                CommentVote::class,
                \get_class($vote)
            ));
        }

        if ($this->submission->getForum()->userIsBanned($vote->getUser())) {
            throw new BannedFromForumException();
        }

        // Only process if this is a new vote (not already in collection)
        if (!$this->votes->contains($vote)) {
            $this->votes->add($vote);
            // New vote: add its effect (+1 for upvote, -1 for downvote)
            $this->netScore += $vote->getChoice();
        }
        // If vote already in collection, do nothing (handled by adjustNetScore for changes)
    }

    public function removeVote(Vote $vote): void {
        if (!$vote instanceof CommentVote) {
            throw new \InvalidArgumentException(sprintf(
                '$vote must be of subtype %s, %s given',
                CommentVote::class,
                \get_class($vote)
            ));
        }

        $this->votes->removeElement($vote);

        // Reverse the vote's effect (+1 upvote removed = -1, -1 downvote removed = +1)
        $this->netScore -= $vote->getChoice();
    }

    /**
     * Adjust netScore by a delta value. Used for vote changes.
     */
    public function adjustNetScore(int $delta): void {
        $this->netScore += $delta;
    }

    public function getVisibility(): string {
        return $this->visibility;
    }

    public function isThreadVisible(): bool {
        if ($this->isVisible()) {
            return true;
        }

        // TODO: avoid doing this more than once for an entire comment tree
        foreach ($this->getChildrenRecursive() as $child) {
            if ($child->isVisible()) {
                return true;
            }
        }

        return false;
    }

    public function isVisibleToUser($user, bool $search = false): bool {
        $visibility = $this->getVisibility();

        if ($search) {
            if ($visibility === self::VISIBILITY_VISIBLE) {
                return true;
            } else if ($visibility === self::VISIBILITY_SOFT_DELETED) {
                return false;
            }
        } else {
            if (\in_array($visibility, [
                self::VISIBILITY_VISIBLE,
                self::VISIBILITY_SOFT_DELETED,
            ], true)) {
                return true;
            }
        }

        if ($user === $this->getUser()) {
            return true;
        }

        return $this->getSubmission()->getForum()->userIsModerator($user);
    }

    public function isThreadVisibleToUser($user): bool {
        $userKey = $user instanceof User ? $user->getId() : -1;
        if (!isset($this->cachedUserThreadVisibilityMap[$userKey])) {
            $this->cacheThreadVisibilitiesForUser($user, $userKey);
        }

        return $this->cachedUserThreadVisibilityMap[$userKey][$this->getId()];
    }

    private function setCachedUserThreadVisibilityMap(
        int $userKey,
        \ArrayObject $threadVisibilityMap
    ): void {
        if (!isset($this->cachedUserThreadVisibilityMap)) {
            $this->cachedUserThreadVisibilityMap = new \ArrayObject();
        }
        $this->cachedUserThreadVisibilityMap[$userKey] = $threadVisibilityMap;
    }

    private function cacheThreadVisibilitiesForUser($user, int $userKey): void {
        $search = [new CommentTree(
            null,
            $this,
            $this->isVisibleToUser($user, true)
        )];
        $threadVisibilityMap = new \ArrayObject();

        for ($parentTree = 0; $parentTree < count($search); $parentTree++) {
            $children = $search[$parentTree]->getComment()->getChildren();

            foreach ($children as $child) {
                $search[] = new CommentTree(
                    $search[$parentTree],
                    $child,
                    $child->isVisibleToUser($user, true)
                );
            }
        }

        for ($childTree = count($search) - 1; $childTree > 0; $childTree--) {
            $visible = $search[$childTree]->getVisible();

            if ($visible) {
                $search[$childTree]->getParent()->setVisible(true);
            }
            $threadVisibilityMap[$search[$childTree]->getComment()->getId()] =
                $visible;

            $search[$childTree]->getComment()
                ->setCachedUserThreadVisibilityMap($userKey, $threadVisibilityMap);
        }
        $threadVisibilityMap[$this->getId()] = $search[0]->getVisible();

        $this->setCachedUserThreadVisibilityMap($userKey, $threadVisibilityMap);
    }

    /**
     * Delete a comment without deleting its replies.
     */
    public function softDelete(): void {
        $this->visibility = self::VISIBILITY_SOFT_DELETED;
        $this->body = '';
        $this->userFlag = UserFlags::FLAG_NONE;
        $this->mentions->clear();
        $this->submission->updateCommentCount();
        $this->submission->updateRanking();
        $this->submission->updateLastActive();
    }

    public function trash(): void {
        $this->visibility = self::VISIBILITY_TRASHED;
        $this->mentions->clear();
        $this->submission->updateCommentCount();
        $this->submission->updateRanking();
        $this->submission->updateLastActive();
    }

    public function restore(): void {
        $this->visibility = self::VISIBILITY_VISIBLE;
        $this->submission->updateCommentCount();
        $this->submission->updateRanking();
        $this->submission->updateLastActive();
    }

    public function getIp(): ?string {
        return $this->ip;
    }

    public function getEditedAt(): ?\DateTimeImmutable {
        return $this->editedAt;
    }

    public function updateEditedAt(): void {
        $this->editedAt = new \DateTimeImmutable('@'.time());
    }

    public function isModerated(): bool {
        return $this->moderated;
    }

    public function setModerated(bool $moderated): void {
        $this->moderated = $moderated;
    }

    public function getUserFlag(): string {
        return $this->userFlag;
    }

    public function setUserFlag(string $userFlag): void {
        UserFlags::checkUserFlag($userFlag);

        $this->userFlag = $userFlag;
    }

    private function notify(): void {
        $receiver = ($this->parent ?: $this->submission)->getUser();

        if (
            $this->user === $receiver ||
            $receiver->isAccountDeleted() ||
            !$receiver->getNotifyOnReply() ||
            $receiver->isBlocking($this->user)
        ) {
            // don't send notifications to oneself, to a user who's disabled
            // them, or to a user who's blocked the user replying
            return;
        }

        $receiver->sendNotification(new CommentNotification($receiver, $this));
    }

    public function getNetScore(): int {
        return $this->netScore;
    }

    public function onCreate(): Event {
        return new CommentCreated($this);
    }

    public function onUpdate($previous): Event {
        \assert($previous instanceof self);

        return new CommentUpdated($previous, $this);
    }

    public function onDelete(): Event {
        return new Event();
    }
}

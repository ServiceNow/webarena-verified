<?php

namespace App\Entity;

use App\Entity\Contracts\DomainEventsInterface as DomainEvents;
use App\Entity\Contracts\VisibilityInterface as Visibility;
use App\Entity\Contracts\Votable;
use App\Entity\Exception\BannedFromForumException;
use App\Entity\Traits\VisibilityTrait;
use App\Entity\Traits\VotableTrait;
use App\Event\SubmissionCreated;
use App\Event\SubmissionUpdated;
use Doctrine\Common\Collections\ArrayCollection;
use Doctrine\Common\Collections\Collection;
use Doctrine\Common\Collections\Criteria;
use Doctrine\Common\Collections\Selectable;
use Doctrine\ORM\Mapping as ORM;
use Symfony\Contracts\EventDispatcher\Event;

/**
 * @ORM\Entity(repositoryClass="App\Repository\SubmissionRepository")
 * @ORM\Table(indexes={
 *     @ORM\Index(name="submissions_timestamp_idx", columns={"timestamp"}),
 *     @ORM\Index(name="submissions_ranking_id_idx", columns={"ranking", "id"}),
 *     @ORM\Index(name="submissions_last_active_id_idx", columns={"last_active", "id"}),
 *     @ORM\Index(name="submissions_comment_count_id_idx", columns={"comment_count", "id"}),
 *     @ORM\Index(name="submissions_net_score_id_idx", columns={"net_score", "id"}),
 *     @ORM\Index(name="submissions_search_idx", columns={"search_doc"}),
 *     @ORM\Index(name="submissions_visibility_idx", columns={"visibility"}),
 *     @ORM\Index(name="submissions_image_id_idx", columns={"image_id"}),
 * })
 */
class Submission implements DomainEvents, Visibility, Votable {
    use VisibilityTrait;
    use VotableTrait {
        getNetScore as private getRealNetScore;
    }

    public const MEDIA_TYPES = [self::MEDIA_URL, self::MEDIA_IMAGE];
    public const MEDIA_URL = 'url';
    public const MEDIA_IMAGE = 'image';

    public const MAX_TITLE_LENGTH = 300;
    public const MAX_URL_LENGTH = 2000;
    public const MAX_BODY_LENGTH = 25000;

    public const FRONT_FEATURED = 'featured';
    public const FRONT_SUBSCRIBED = 'subscribed';
    public const FRONT_ALL = 'all';
    public const FRONT_MODERATED = 'moderated';
    public const SORT_ACTIVE = 'active';
    public const SORT_HOT = 'hot';
    public const SORT_NEW = 'new';
    public const SORT_TOP = 'top';
    public const SORT_CONTROVERSIAL = 'controversial';
    public const SORT_MOST_COMMENTED = 'most_commented';
    public const TIME_DAY = 'day';
    public const TIME_WEEK = 'week';
    public const TIME_MONTH = 'month';
    public const TIME_YEAR = 'year';
    public const TIME_ALL = 'all';

    public const FRONT_PAGE_OPTIONS = [
        self::FRONT_FEATURED,
        self::FRONT_SUBSCRIBED,
        self::FRONT_ALL,
        self::FRONT_MODERATED,
    ];

    public const SORT_OPTIONS = [
        self::SORT_ACTIVE,
        self::SORT_HOT,
        self::SORT_NEW,
        self::SORT_TOP,
        self::SORT_CONTROVERSIAL,
        self::SORT_MOST_COMMENTED,
    ];

    public const TIME_OPTIONS = [
        self::TIME_DAY,
        self::TIME_WEEK,
        self::TIME_MONTH,
        self::TIME_YEAR,
        self::TIME_ALL,
    ];

    private const DOWNVOTED_CUTOFF = -5;
    private const NETSCORE_MULTIPLIER = 1800;
    private const COMMENT_MULTIPLIER = 5000;
    private const COMMENT_DOWNVOTED_MULTIPLIER = 500;
    private const MAX_ADVANTAGE = 86400;
    private const MAX_PENALTY = 43200;

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
    private $title;

    /**
     * @ORM\Column(type="text", nullable=true)
     *
     * @var string|null
     */
    private $url;

    /**
     * @ORM\Column(type="text", nullable=true)
     *
     * @var string|null
     */
    private $body;

    /**
     * @ORM\Column(type="text")
     *
     * @var string
     */
    private $mediaType = self::MEDIA_URL;

    /**
     * @ORM\OneToMany(targetEntity="Comment", mappedBy="submission",
     *     fetch="EXTRA_LAZY", cascade={"remove"})
     * @ORM\OrderBy({"timestamp": "ASC"})
     *
     * @var Collection<array-key, Comment>&Selectable<array-key, Comment>
     */
    private $comments;

    /**
     * @ORM\Column(type="integer")
     *
     * @var int
     */
    private $commentCount = 0;

    /**
     * @ORM\Column(type="datetimetz_immutable")
     *
     * @var \DateTimeImmutable
     */
    private $timestamp;

    /**
     * @ORM\Column(type="datetimetz_immutable")
     *
     * @var \DateTimeImmutable
     */
    private $lastActive;

    /**
     * @ORM\Column(type="text", options={"default": "visible"})
     *
     * @var string
     */
    private $visibility = self::VISIBILITY_VISIBLE;

    /**
     * @ORM\JoinColumn(nullable=false)
     * @ORM\ManyToOne(targetEntity="Forum", inversedBy="submissions")
     *
     * @var Forum
     */
    private $forum;

    /**
     * @ORM\JoinColumn(nullable=false)
     * @ORM\ManyToOne(targetEntity="User", inversedBy="submissions")
     *
     * @var User
     */
    private $user;

    /**
     * @ORM\OneToMany(targetEntity="SubmissionVote", mappedBy="submission",
     *     fetch="EXTRA_LAZY", cascade={"persist"}, orphanRemoval=true)
     *
     * @var Collection<array-key, SubmissionVote>&Selectable<array-key, SubmissionVote>
     */
    private $votes;

    /**
     * @ORM\OneToMany(targetEntity="SubmissionMention", mappedBy="submission", cascade={"remove"}, orphanRemoval=true)
     *
     * @var Collection<array-key, SubmissionMention>&Selectable<array-key, SubmissionMention>
     */
    private $mentions;

    /**
     * @ORM\ManyToOne(targetEntity="Image", cascade={"persist"})
     *
     * @var Image|null
     */
    private $image;

    /**
     * @ORM\Column(type="inet", nullable=true)
     *
     * @var string|null
     */
    private $ip;

    /**
     * @ORM\Column(type="boolean")
     *
     * @var bool
     */
    private $sticky = false;

    /**
     * @ORM\Column(type="bigint")
     *
     * @var int
     */
    private $ranking;

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
     * @ORM\Column(type="boolean", options={"default": false})
     *
     * @var bool
     */
    private $locked = false;

    /**
     * @ORM\Column(type="integer")
     *
     * @var int
     */
    private $netScore = 0;

    /**
     * @ORM\JoinTable(name="submissions_flairs", joinColumns={
     *     @ORM\JoinColumn(name="submission_id", referencedColumnName="id"),
     * }, inverseJoinColumns={
     *     @ORM\JoinColumn(name="flair_id", referencedColumnName="id"),
     * })
     * @ORM\ManyToMany(targetEntity="Flair", cascade={"persist", "remove"})
     *
     * @var Collection<array-key, Flair>&Selectable<array-key, Flair>
     */
    private $flairs;

    /**
     * @ORM\Column(type="tsvector", nullable=true)
     *
     * @var string
     */
    private $searchDoc;

    public function __construct(
        string $title,
        ?string $url,
        ?string $body,
        Forum $forum,
        User $user,
        ?string $ip
    ) {
        if ($ip !== null && !filter_var($ip, FILTER_VALIDATE_IP)) {
            throw new \InvalidArgumentException("Invalid IP address '$ip'");
        }

        if ($forum->userIsBanned($user)) {
            throw new BannedFromForumException();
        }

        $this->title = $title;
        $this->url = $url;
        $this->body = $body;
        $this->forum = $forum;
        $this->user = $user;
        $this->ip = $user->isWhitelistedOrAdmin() ? null : $ip;
        $this->timestamp = new \DateTimeImmutable('@'.time());
        $this->comments = new ArrayCollection();
        $this->votes = new ArrayCollection();
        $this->mentions = new ArrayCollection();
        $this->flairs = new ArrayCollection();
        $this->addVote($this->createVote(self::VOTE_UP, $user, $ip));
        $this->updateLastActive();
        $forum->addSubmission($this);
        $user->addSubmission($this);
    }

    public function getId(): ?int {
        return $this->id;
    }

    public function getTitle(): string {
        return $this->title;
    }

    public function setTitle(string $title): void {
        $this->title = $title;
    }

    public function getUrl(): ?string {
        return $this->url;
    }

    public function setUrl(?string $url): void {
        $this->url = $url;
    }

    public function getBody(): ?string {
        return $this->body;
    }

    public function setBody(?string $body): void {
        $this->body = $body;
    }

    public function getMediaType(): string {
        return $this->mediaType;
    }

    public function setMediaType(string $mediaType): void {
        if (!\in_array($mediaType, self::MEDIA_TYPES, true)) {
            throw new \InvalidArgumentException("Bad media type '$mediaType'");
        }

        if ($mediaType === self::MEDIA_IMAGE && $this->url !== null) {
            throw new \BadMethodCallException(
                'Submission with URL cannot have image as media type'
            );
        }

        $this->mediaType = $mediaType;
    }

    /**
     * Get all comments, ordered by ascending time of creation.
     *
     * @return Comment[]
     */
    public function getComments(): array {
        $criteria = Criteria::create()
            ->where(Criteria::expr()->eq('visibility', Comment::VISIBILITY_VISIBLE))
            ->orderBy(['timestamp' => 'ASC']);

        return $this->comments->matching($criteria)->toArray();
    }

    /**
     * Get top-level comments, ordered by descending net score.
     *
     * @return Comment[]
     */
    public function getTopLevelComments(): array {
        $criteria = Criteria::create()
            ->where(Criteria::expr()->isNull('parent'))
            ->andWhere(Criteria::expr()->eq('visibility', Comment::VISIBILITY_VISIBLE));

        $comments = $this->comments->matching($criteria)->toArray();

        usort($comments, static function (Comment $a, Comment $b) {
            return $b->getNetScore() <=> $a->getNetScore();
        });

        return $comments;
    }

    public function hasVisibleComments(): bool {
        $criteria = Criteria::create()
            ->where(Criteria::expr()->eq('visibility', Comment::VISIBILITY_VISIBLE))
            ->setMaxResults(1);

        return \count($this->comments->matching($criteria)) > 0;
    }

    public function addComment(Comment ...$comments): void {
        foreach ($comments as $comment) {
            if (!$this->comments->contains($comment)) {
                $this->comments->add($comment);
            }
        }

        $this->updateCommentCount();
        $this->updateRanking();
        $this->updateLastActive();
    }

    public function removeComment(Comment ...$comments): void {
        // hydrate the collection
        $this->comments->get(-1);

        foreach ($comments as $comment) {
            if ($this->comments->contains($comment)) {
                $this->comments->removeElement($comment);
            }
        }

        $this->updateCommentCount();
        $this->updateRanking();
        $this->updateLastActive();
    }

    public function getCommentCount(): int {
        return $this->commentCount;
    }

    public function updateCommentCount(): void {
        // hydrate the collection
        $this->comments->get(-1);

        $criteria = Criteria::create()
            ->where(Criteria::expr()->eq('visibility', Comment::VISIBILITY_VISIBLE));

        $this->commentCount = \count($this->comments->matching($criteria));
    }

    public function getTimestamp(): \DateTimeImmutable {
        return $this->timestamp;
    }

    public function getLastActive(): \DateTimeImmutable {
        return $this->lastActive;
    }

    public function updateLastActive(): void {
        // hydrate the collection
        $this->comments->get(-1);

        $criteria = Criteria::create()
            ->where(Criteria::expr()->eq('visibility', Comment::VISIBILITY_VISIBLE))
            ->orderBy(['timestamp' => 'DESC'])
            ->setMaxResults(1);

        $lastComment = $this->comments->matching($criteria)->first();
        \assert($lastComment instanceof Comment || !$lastComment);

        if ($lastComment) {
            $this->lastActive = $lastComment->getTimestamp();
        } else {
            $this->lastActive = $this->getTimestamp();
        }
    }

    public function getVisibility(): string {
        return $this->visibility;
    }

    public function softDelete(): void {
        $this->visibility = self::VISIBILITY_SOFT_DELETED;
        $this->title = '';
        $this->mediaType = self::MEDIA_URL;
        $this->url = null;
        $this->body = null;
        $this->image = null;
        $this->sticky = false;
        $this->userFlag = UserFlags::FLAG_NONE;
        $this->mentions->clear();
    }

    public function trash(): void {
        $this->visibility = self::VISIBILITY_TRASHED;
        $this->sticky = false;
        $this->mentions->clear();
    }

    public function restore(): void {
        if (!\in_array($this->visibility, [
            self::VISIBILITY_VISIBLE,
            self::VISIBILITY_TRASHED,
        ], true)) {
            throw new \DomainException(sprintf(
                'Cannot restore a submission in the "%s" state',
                $this->visibility,
            ));
        }

        $this->visibility = self::VISIBILITY_VISIBLE;
    }

    public function getForum(): Forum {
        return $this->forum;
    }

    public function getUser(): User {
        return $this->user;
    }

    /**
     * @return Collection<array-key, SubmissionVote>&Selectable<array-key, SubmissionVote>
     */
    protected function getVotes(): Collection {
        return $this->votes;
    }

    public function createVote(int $choice, User $user, ?string $ip): Vote {
        return new SubmissionVote($choice, $user, $ip, $this);
    }

    public function addVote(Vote $vote): void {
        if (!$vote instanceof SubmissionVote) {
            throw new \InvalidArgumentException(sprintf(
                '$vote must be of subtype %s, %s given',
                SubmissionVote::class,
                \get_class($vote)
            ));
        }

        if (
            $vote->getChoice() !== self::VOTE_NONE &&
            $this->forum->userIsBanned($vote->getUser())
        ) {
            throw new BannedFromForumException();
        }

        // Only process if this is a new vote (not already in collection)
        if (!$this->votes->contains($vote)) {
            $this->votes->add($vote);
            // New vote: add its effect (+1 for upvote, -1 for downvote)
            $this->netScore += $vote->getChoice();
            $this->updateRanking();
        }
        // If vote already in collection, do nothing (handled by adjustNetScore for changes)
    }

    /**
     * Adjust netScore by a delta value. Used for vote changes.
     */
    public function adjustNetScore(int $delta): void {
        $this->netScore += $delta;
        $this->updateRanking();
    }

    public function removeVote(Vote $vote): void {
        if (!$vote instanceof SubmissionVote) {
            throw new \InvalidArgumentException(sprintf(
                '$vote must be of subtype %s, %s given',
                SubmissionVote::class,
                \get_class($vote)
            ));
        }

        $this->votes->removeElement($vote);

        // Reverse the vote's effect (+1 upvote removed = -1, -1 downvote removed = +1)
        $this->netScore -= $vote->getChoice();

        $this->updateRanking();
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

        $mentioned->sendNotification(new SubmissionMention($mentioned, $this));
    }

    public function getImage(): ?Image {
        return $this->image;
    }

    public function setImage(?Image $image): void {
        $this->image = $image;
    }

    public function getIp(): ?string {
        return $this->ip;
    }

    public function isSticky(): bool {
        return $this->sticky;
    }

    public function setSticky(bool $sticky): void {
        $this->sticky = $sticky;
    }

    public function getRanking(): int {
        return $this->ranking;
    }

    public function updateRanking(): void {
        $netScore = $this->getNetScore();
        $netScoreAdvantage = $netScore * self::NETSCORE_MULTIPLIER;

        if ($netScore > self::DOWNVOTED_CUTOFF) {
            $commentAdvantage = $this->getCommentCount() * self::COMMENT_MULTIPLIER;
        } else {
            $commentAdvantage = $this->getCommentCount() * self::COMMENT_DOWNVOTED_MULTIPLIER;
        }

        $advantage = max(min($netScoreAdvantage + $commentAdvantage, self::MAX_ADVANTAGE), -self::MAX_PENALTY);

        $this->ranking = $this->getTimestamp()->getTimestamp() + $advantage;
    }

    public function getEditedAt(): ?\DateTimeImmutable {
        return $this->editedAt;
    }

    public function setEditedAt(?\DateTimeInterface $editedAt): void {
        if ($editedAt instanceof \DateTime) {
            $editedAt = \DateTimeImmutable::createFromMutable($editedAt);
        }

        $this->editedAt = $editedAt;
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

    public function isLocked(): bool {
        return $this->locked;
    }

    public function setLocked(bool $locked): void {
        $this->locked = $locked;
    }

    public function getNetScore(): int {
        return $this->netScore;
    }

    /**
     * @return Flair[]
     */
    public function getFlairs(): array {
        return $this->flairs->getValues();
    }

    public function addFlair(Flair $flair): void {
        if (!$this->flairs->contains($flair)) {
            $this->flairs->add($flair);
        }
    }

    public function removeFlair(Flair $flair): void {
        $this->flairs->removeElement($flair);
    }

    public function onCreate(): Event {
        return new SubmissionCreated($this);
    }

    public function onUpdate($previous): Event {
        \assert($previous instanceof self);

        return new SubmissionUpdated($previous, $this);
    }

    /**
     * use {@link DeleteSubmission} with negative priority instead
     */
    public function onDelete(): Event {
        return new Event();
    }
}

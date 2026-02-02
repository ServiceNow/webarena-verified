<?php

namespace App\DataObject;

use App\Entity\Forum;
use App\Entity\Image;
use App\Entity\Submission;
use App\Entity\User;
use App\Entity\UserFlags;
use App\Serializer\Contracts\NormalizeMarkdownInterface;
use App\Validator\NoBadPhrases;
use App\Validator\NotForumBanned;
use App\Validator\RateLimit;
use Symfony\Component\Serializer\Annotation\Groups;
use Symfony\Component\Validator\Constraints as Assert;

/**
 */
class SubmissionData implements NormalizeMarkdownInterface {
    /**
     * @Groups({"submission:read", "abbreviated_relations"})
     *
     * @var int|null
     */
    private $id;

    /**
     * @Assert\NotBlank(groups={"create", "update"})
     * @Assert\Length(max=Submission::MAX_TITLE_LENGTH, groups={"create", "update"})
     * @NoBadPhrases(groups={"create", "update"})
     *
     * @Groups({"submission:read", "submission:create", "submission:update"})
     *
     * @var string|null
     */
    private $title;

    /**
     * @Assert\Length(max=Submission::MAX_URL_LENGTH, charset="8bit", groups={"url"})
     * @Assert\Url(protocols={"http", "https"}, groups={"url"})
     * @NoBadPhrases(groups={"url"})
     *
     * @Groups({"submission:read", "submission:create", "submission:update"})
     *
     * @see https://stackoverflow.com/questions/417142/
     *
     * @var string|null
     */
    private $url;

    /**
     * @Assert\Length(max=Submission::MAX_BODY_LENGTH, groups={"create", "update"})
     * @NoBadPhrases(groups={"create", "update"})
     *
     * @Groups({"submission:read", "submission:create", "submission:update"})
     *
     * @var string|null
     */
    private $body;

    /**
     * @Assert\Choice(Submission::MEDIA_TYPES, groups={"media"})
     * @Assert\NotBlank(groups={"media"})
     *
     * @Groups("submission:read")
     *
     * @var string|null
     */
    private $mediaType = Submission::MEDIA_URL;

    /**
     * @Groups("submission:read")
     *
     * @var int
     */
    private $commentCount = 0;

    /**
     * @Groups("submission:read")
     *
     * @var \DateTimeImmutable|null
     */
    private $timestamp;

    /**
     * @Groups("submission:read")
     *
     * @var \DateTimeImmutable|null
     */
    private $lastActive;

    /**
     * @Groups("submission:read")
     *
     * @var string
     */
    private $visibility;

    /**
     * @NotForumBanned(groups={"create", "update"})
     * @Assert\NotBlank(groups={"create"})
     *
     * @Groups({"submission:read", "submission:create", "abbreviated_relations"})
     *
     * @var Forum|null
     */
    private $forum;

    /**
     * @Groups({"submission:read", "abbreviated_relations"})
     *
     * @var User
     */
    private $user;

    /**
     * @Groups("submission:read")
     *
     * @var int
     */
    private $netScore = 0;

    /**
     * @Groups("submission:read")
     *
     * @var int
     */
    private $upvotes = 0;

    /**
     * @Groups("submission:read")
     *
     * @var int
     */
    private $downvotes = 0;

    /**
     * @Groups("submission:read")
     *
     * @var Image|null
     */
    private $image;

    /**
     * @Groups("submission:read")
     *
     * @var bool
     */
    private $sticky = false;

    /**
     * @Groups("submission:read")
     *
     * @var \DateTimeImmutable|null
     */
    private $editedAt;

    /**
     * @Groups("submission:read")
     *
     * @var bool
     */
    private $moderated = false;

    /**
     * @Groups("submission:read")
     *
     * @var string
     */
    private $userFlag = UserFlags::FLAG_NONE;

    /**
     * @Groups("submission:read")
     *
     * @var bool
     */
    private $locked = false;

    public static function createFromSubmission(Submission $submission): self {
        $self = new self();
        $self->id = $submission->getId();
        $self->title = $submission->getTitle();
        $self->url = $submission->getUrl();
        $self->body = $submission->getBody();
        $self->mediaType = $submission->getMediaType();
        $self->commentCount = $submission->getCommentCount();
        $self->timestamp = $submission->getTimestamp();
        $self->lastActive = $submission->getLastActive();
        $self->visibility = $submission->getVisibility();
        $self->forum = $submission->getForum();
        $self->user = $submission->getUser();
        $self->netScore = $submission->getNetScore();
        $self->upvotes = $submission->getUpvotes();
        $self->downvotes = $submission->getDownvotes();
        $self->image = $submission->getImage();
        $self->sticky = $submission->isSticky();
        $self->editedAt = $submission->getEditedAt();
        $self->moderated = $submission->isModerated();
        $self->userFlag = $submission->getUserFlag();
        $self->locked = $submission->isLocked();

        return $self;
    }

    public function getId(): ?int {
        return $this->id;
    }

    public function getTitle(): ?string {
        return $this->title;
    }

    public function setTitle(?string $title): void {
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

    public function getMediaType(): ?string {
        return $this->mediaType;
    }

    public function setMediaType(string $mediaType): void {
        $this->mediaType = $mediaType;
    }

    public function getCommentCount(): int {
        return $this->commentCount;
    }

    public function getTimestamp(): ?\DateTimeImmutable {
        return $this->timestamp;
    }

    public function getLastActive(): ?\DateTimeImmutable {
        return $this->lastActive;
    }

    public function getVisibility(): ?string {
        return $this->visibility;
    }

    public function getForum(): ?Forum {
        return $this->forum;
    }

    public function setForum(?Forum $forum): void {
        $this->forum = $forum;
    }

    public function getUser(): ?User {
        return $this->user;
    }

    public function getNetScore(): int {
        return $this->netScore;
    }

    public function getUpvotes(): int {
        return $this->upvotes;
    }

    public function getDownvotes(): int {
        return $this->downvotes;
    }

    public function getImage(): ?Image {
        return $this->image;
    }

    public function setImage(?Image $image): void {
        $this->image = $image;
    }

    public function isSticky(): bool {
        return $this->sticky;
    }

    public function setSticky(bool $sticky): void {
        $this->sticky = $sticky;
    }

    public function getEditedAt(): ?\DateTimeImmutable {
        return $this->editedAt;
    }

    public function isModerated(): bool {
        return $this->moderated;
    }

    public function getUserFlag(): string {
        return $this->userFlag;
    }

    public function setUserFlag(?string $userFlag): void {
        $this->userFlag = $userFlag;
    }

    public function isLocked(): bool {
        return $this->locked;
    }

    public function setLocked(bool $locked): void {
        $this->locked = $locked;
    }

    public function getMarkdownFields(): iterable {
        yield 'body';
    }
}

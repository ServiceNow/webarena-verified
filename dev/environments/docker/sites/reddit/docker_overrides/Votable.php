<?php

namespace App\Entity\Contracts;

use App\Entity\User;
use App\Entity\Vote;

interface Votable {
    public const VOTE_UP = 1;
    public const VOTE_NONE = 0;
    public const VOTE_DOWN = -1;

    public function getDownvotes(): int;

    public function getNetScore(): int;

    public function getUpvotes(): int;

    public function getUserChoice(User $user): int;

    public function getUserVote(User $user): ?Vote;

    public function createVote(int $choice, User $user, ?string $ip): Vote;

    public function addVote(Vote $vote): void;

    public function removeVote(Vote $vote): void;

    public function adjustNetScore(int $delta): void;
}

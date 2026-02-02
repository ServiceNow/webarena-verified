<?php

namespace App\DataTransfer;

use App\Entity\Contracts\Votable;
use App\Entity\User;
use Doctrine\ORM\EntityManagerInterface;

/**
 * Modified VoteManager to use increment/decrement instead of recalculating netScore.
 * This preserves imported netScore values that don't have corresponding vote records.
 */
class VoteManager {
    private $entityManager;

    public function __construct(EntityManagerInterface $entityManager) {
        $this->entityManager = $entityManager;
    }

    public function vote(Votable $votable, User $user, int $choice, ?string $ip): void {
        $vote = $votable->getUserVote($user);

        if ($vote) {
            if ($choice === Votable::VOTE_NONE) {
                // Retract vote
                $votable->removeVote($vote);
                $this->entityManager->remove($vote);
            } elseif ($choice !== $vote->getChoice()) {
                // Vote change: adjust netScore by the delta (e.g., +1 to -1 = -2)
                $oldChoice = $vote->getChoice();
                $vote->setChoice($choice);
                $votable->adjustNetScore($choice - $oldChoice);
            }
            // If same choice, do nothing
        } elseif ($choice !== Votable::VOTE_NONE) {
            // New vote: createVote calls addVote internally via constructor
            $vote = $votable->createVote($choice, $user, $ip);
            $this->entityManager->persist($vote);
        }

        $this->entityManager->flush();
    }
}

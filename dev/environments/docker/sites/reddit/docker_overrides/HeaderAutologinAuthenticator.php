<?php

namespace App\Security;

use App\Entity\User;
use Doctrine\ORM\EntityManagerInterface;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\Security\Core\Authentication\Token\TokenInterface;
use Symfony\Component\Security\Core\Exception\AuthenticationException;
use Symfony\Component\Security\Core\Exception\UserNotFoundException;
use Symfony\Component\Security\Http\Authenticator\AbstractAuthenticator;
use Symfony\Component\Security\Http\Authenticator\Passport\Badge\UserBadge;
use Symfony\Component\Security\Http\Authenticator\Passport\Credentials\PasswordCredentials;
use Symfony\Component\Security\Http\Authenticator\Passport\Passport;

/**
 * Authenticator that allows authentication via X-Postmill-Auto-Login header.
 *
 * Usage: Add header "X-Postmill-Auto-Login: username:password" to authenticate as that user.
 * The password is validated against the stored hash.
 *
 * WARNING: This should only be used in test environments!
 */
class HeaderAutologinAuthenticator extends AbstractAuthenticator {
    private const HEADER_NAME = 'X-Postmill-Auto-Login';

    private EntityManagerInterface $entityManager;

    public function __construct(EntityManagerInterface $entityManager) {
        $this->entityManager = $entityManager;
    }

    public function supports(Request $request): ?bool {
        return $request->headers->has(self::HEADER_NAME);
    }

    public function authenticate(Request $request): Passport {
        $headerValue = $request->headers->get(self::HEADER_NAME);

        if (!$headerValue) {
            throw new AuthenticationException('No credentials provided in ' . self::HEADER_NAME . ' header');
        }

        // Parse username:password format
        $parts = explode(':', $headerValue, 2);
        if (count($parts) !== 2) {
            throw new AuthenticationException('Invalid format in ' . self::HEADER_NAME . ' header. Expected username:password');
        }

        $username = $parts[0];
        $password = $parts[1];

        if (!$username) {
            throw new AuthenticationException('No username provided in ' . self::HEADER_NAME . ' header');
        }

        if (!$password) {
            throw new AuthenticationException('No password provided in ' . self::HEADER_NAME . ' header');
        }

        return new Passport(
            new UserBadge($username, function (string $userIdentifier): User {
                $user = $this->entityManager
                    ->getRepository(User::class)
                    ->loadUserByUsername($userIdentifier);

                if (!$user) {
                    throw new UserNotFoundException(sprintf('User "%s" not found.', $userIdentifier));
                }

                return $user;
            }),
            new PasswordCredentials($password)
        );
    }

    public function onAuthenticationSuccess(Request $request, TokenInterface $token, string $firewallName): ?Response {
        // Continue with the request
        return null;
    }

    public function onAuthenticationFailure(Request $request, AuthenticationException $exception): ?Response {
        return new Response(
            'Authentication failed: ' . $exception->getMessage(),
            Response::HTTP_UNAUTHORIZED
        );
    }
}

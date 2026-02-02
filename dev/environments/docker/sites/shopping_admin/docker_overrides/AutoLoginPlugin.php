<?php

namespace WebArena\AutoLogin\Plugin;

use Magento\Framework\App\FrontControllerInterface;
use Magento\Framework\App\RequestInterface;
use Magento\Framework\App\State;
use Magento\Backend\Model\Auth;
use Psr\Log\LoggerInterface;

/**
 * Plugin that intercepts admin requests and performs auto-login via HTTP header.
 *
 * This plugin checks for the X-M2-Admin-Auto-Login header on admin area requests
 * and automatically logs in the user if credentials are valid using Magento's
 * official Auth::login() API.
 *
 * Advantages over Observer approach:
 * - Works with setup:di:compile instead of setup:upgrade (faster)
 * - Intercepts requests before controller dispatch
 * - No event system dependencies
 * - Uses official Magento Auth API for proper login flow
 */
class AutoLoginPlugin
{
    /**
     * HTTP header name for auto-login credentials
     */
    const AUTO_LOGIN_HEADER = 'X-M2-Admin-Auto-Login';

    /**
     * @var Auth
     */
    protected $auth;

    /**
     * @var State
     */
    protected $appState;

    /**
     * @var LoggerInterface
     */
    protected $logger;

    /**
     * @param Auth $auth
     * @param State $appState
     * @param LoggerInterface $logger
     */
    public function __construct(
        Auth $auth,
        State $appState,
        LoggerInterface $logger
    ) {
        $this->auth = $auth;
        $this->appState = $appState;
        $this->logger = $logger;
    }

    /**
     * Before front controller dispatch, check for auto-login header.
     *
     * @param FrontControllerInterface $subject
     * @param RequestInterface $request
     * @return void
     */
    public function beforeDispatch(
        FrontControllerInterface $subject,
        RequestInterface $request
    ) {
        // Only process admin area requests
        try {
            $areaCode = $this->appState->getAreaCode();
            if ($areaCode !== \Magento\Framework\App\Area::AREA_ADMINHTML) {
                return;
            }
        } catch (\Exception $e) {
            // Area not set yet, skip
            return;
        }

        // Check if user is already logged in
        if ($this->auth->isLoggedIn()) {
            return;
        }

        // Check for auto-login header
        $credentials = $request->getHeader(self::AUTO_LOGIN_HEADER);
        if (!$credentials) {
            return;
        }

        // Parse username:password format
        $parts = explode(':', $credentials, 2);
        if (count($parts) !== 2) {
            $this->logger->warning('Auto-login header must be in format username:password');
            return;
        }

        list($username, $password) = $parts;

        // Validate both username and password are present
        if (empty($username) || empty($password)) {
            $this->logger->warning('Auto-login username and password cannot be empty');
            return;
        }

        try {
            // Use official Magento Auth API to login
            // This properly handles all validation, events, and session setup
            $this->auth->login($username, $password);

            // Log the successful auto-login
            $this->logger->info('Auto-login successful for user: ' . $username);

        } catch (\Magento\Framework\Exception\AuthenticationException $e) {
            // Authentication failed (invalid username/password, inactive user, etc.)
            $this->logger->warning('Auto-login authentication failed: ' . $e->getMessage());
        } catch (\Exception $e) {
            // Other errors (ReCaptcha, TFA, etc.)
            $this->logger->error('Auto-login failed: ' . $e->getMessage());
        }
    }
}

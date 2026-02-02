<?php

namespace WebArena\CustomerAutoLogin\Plugin;

use Magento\Customer\Api\AccountManagementInterface;
use Magento\Customer\Model\Session as CustomerSession;
use Magento\Framework\App\FrontControllerInterface;
use Magento\Framework\App\RequestInterface;
use Magento\Framework\App\State;
use Psr\Log\LoggerInterface;

/**
 * Plugin that intercepts frontend requests and performs customer auto-login via HTTP header.
 *
 * This plugin checks for the X-M2-Customer-Auto-Login header on frontend requests
 * and automatically logs in the customer if credentials are valid.
 */
class CustomerAutoLoginPlugin
{
    /**
     * HTTP header name for auto-login credentials
     */
    const AUTO_LOGIN_HEADER = 'X-M2-Customer-Auto-Login';

    /**
     * @var CustomerSession
     */
    protected $customerSession;

    /**
     * @var AccountManagementInterface
     */
    protected $accountManagement;

    /**
     * @var State
     */
    protected $appState;

    /**
     * @var LoggerInterface
     */
    protected $logger;

    /**
     * @param CustomerSession $customerSession
     * @param AccountManagementInterface $accountManagement
     * @param State $appState
     * @param LoggerInterface $logger
     */
    public function __construct(
        CustomerSession $customerSession,
        AccountManagementInterface $accountManagement,
        State $appState,
        LoggerInterface $logger
    ) {
        $this->customerSession = $customerSession;
        $this->accountManagement = $accountManagement;
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
        // Only process frontend area requests
        try {
            $areaCode = $this->appState->getAreaCode();
            if ($areaCode !== \Magento\Framework\App\Area::AREA_FRONTEND) {
                return;
            }
        } catch (\Exception $e) {
            // Area not set yet, skip
            return;
        }

        // Check if customer is already logged in
        if ($this->customerSession->isLoggedIn()) {
            return;
        }

        // Check for auto-login header
        $credentials = $request->getHeader(self::AUTO_LOGIN_HEADER);
        if (!$credentials) {
            return;
        }

        // Parse email:password format
        $parts = explode(':', $credentials, 2);
        if (count($parts) !== 2) {
            $this->logger->warning('Customer auto-login header must be in format email:password');
            return;
        }

        list($email, $password) = $parts;

        // Validate both email and password are present
        if (empty($email) || empty($password)) {
            $this->logger->warning('Customer auto-login email and password cannot be empty');
            return;
        }

        try {
            // Authenticate customer using Magento's official API
            $customer = $this->accountManagement->authenticate($email, $password);

            // Login the customer
            $this->customerSession->setCustomerDataAsLoggedIn($customer);

            $this->logger->info('Customer auto-login successful for: ' . $email);

        } catch (\Magento\Framework\Exception\InvalidEmailOrPasswordException $e) {
            $this->logger->warning('Customer auto-login failed - invalid credentials for: ' . $email);
        } catch (\Exception $e) {
            $this->logger->error('Customer auto-login failed: ' . $e->getMessage());
        }
    }
}

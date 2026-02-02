<?php
declare(strict_types=1);

namespace WebArena\AutoLogin\Plugin;

use Magento\Catalog\Ui\Component\Product\MassAction;

/**
 * Plugin to disable "Update Attributes" mass action in product grid
 */
class DisableProductMassActionsPlugin
{
    /**
     * Disabled action types
     */
    private const DISABLED_ACTIONS = [
        'attributes', // "Update Attributes" action
        'delete'      // "Delete" action
    ];

    /**
     * After plugin to disable specific mass actions
     *
     * @param MassAction $subject
     * @param bool $isAllowed
     * @param string $actionType
     * @return bool
     */
    public function afterIsActionAllowed(
        MassAction $subject,
        bool $isAllowed,
        string $actionType
    ): bool {
        if (in_array($actionType, self::DISABLED_ACTIONS, true)) {
            return false;
        }
        return $isAllowed;
    }
}

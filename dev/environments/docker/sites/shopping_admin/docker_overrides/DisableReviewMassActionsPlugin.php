<?php
declare(strict_types=1);

namespace WebArena\AutoLogin\Plugin;

use Magento\Review\Block\Adminhtml\Grid;

/**
 * Plugin to disable "Update Status" mass action in review grid
 */
class DisableReviewMassActionsPlugin
{
    /**
     * Disabled mass action IDs
     */
    private const DISABLED_ACTIONS = [
        'update_status', // "Update Status" action
        'delete'         // "Delete" action
    ];

    /**
     * After plugin to remove specific mass actions from the grid
     *
     * @param Grid $subject
     * @param Grid $result
     * @return Grid
     */
    public function afterGetMassactionBlock(Grid $subject, $result)
    {
        if ($result) {
            foreach (self::DISABLED_ACTIONS as $actionId) {
                $result->removeItem($actionId);
            }
        }
        return $result;
    }
}

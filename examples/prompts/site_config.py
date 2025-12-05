"""Site-specific metadata for prompt generation."""

from webarena_verified.types.config import WebArenaSite

SITE_METADATA = {
    WebArenaSite.SHOPPING: {
        "platform_name": "E-commerce Store",
        "description": "An online shopping platform where customers can browse products, add items to cart, and make purchases.",
        "auth": "You are already logged in as emma.lopez@gmail.com. To re-authenticate, use credentials: emma.lopez@gmail.com / Password.123. If re-authentication fails, terminate with PERMISSION_DENIED_ERROR status.",
    },
    WebArenaSite.REDDIT: {
        "platform_name": "Discussion Forum",
        "description": "A social news aggregation, content rating, and discussion website where users can post content and vote on submissions.",
        "auth": "You are already logged in as MarvelsGrantMan136. To re-authenticate, use credentials: MarvelsGrantMan136 / test1234. If re-authentication fails, terminate with PERMISSION_DENIED_ERROR status.",
    },
    WebArenaSite.GITLAB: {
        "platform_name": "GitLab",
        "description": "A web-based Git repository manager providing wiki, issue tracking, and CI/CD pipeline features.",
        "auth": "You are already logged in as byteblaze. To re-authenticate, use credentials: byteblaze / hello1234. If re-authentication fails, terminate with PERMISSION_DENIED_ERROR status.",
    },
    WebArenaSite.SHOPPING_ADMIN: {
        "platform_name": "Merchant Admin Portal",
        "description": "An admin portal to manage an e-commerce business.",
        "auth": "You are already logged in as admin. To re-authenticate, use credentials: admin / admin1234. If re-authentication fails, terminate with PERMISSION_DENIED_ERROR status.",
    },
    WebArenaSite.MAP: {
        "platform_name": "Map Service",
        "description": "An interactive map platform for searching locations, getting directions, and exploring geographic information.",
        "auth": "No authentication required. However, assume that I'm located in Pennsylvania, USA.",
    },
    WebArenaSite.WIKIPEDIA: {
        "platform_name": "Wikipedia",
        "description": "A free online encyclopedia with user-contributed content.",
        "auth": "No authentication required.",
    },
}

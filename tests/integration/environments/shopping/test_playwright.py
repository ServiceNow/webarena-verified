"""Playwright UI tests for Shopping Docker container.

Tests the Magento storefront functionality using browser automation.

Test categories:
- Customer Login: Authentication flow
- Storefront Navigation: Category and product browsing
- Search: Product search functionality
- Cart: Add to cart functionality
- Image Loading: Product image verification

Usage:
    pytest tests/integration/environments/shopping/test_playwright.py
    pytest tests/integration/environments/shopping/test_playwright.py --playwright-timeout-sec=60
"""

import urllib.request

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.docker, pytest.mark.integration_docker_shopping]

# Magento placeholder image size in bytes (used to detect missing images)
PLACEHOLDER_IMAGE_SIZE = 1692

# Known products in the shopping dataset (One Stop Market)
TEST_PRODUCT_URL = "toothbrush-head-cover-toothbrush-protective-case-toothbrush-head-cap-for-home-travel-camping-lightweight-safe-protecting-toothbrush-head-light-blue.html"
TEST_PRODUCT_NAME = "Toothbrush Head Cover"
TEST_CATEGORY_URL = "beauty-personal-care.html"
TEST_SEARCH_TERM = "toothbrush"


# Customer Login Tests


@pytest.mark.flaky(reruns=2)
def test_customer_login(shopping_container, shopping_base_url, shopping_credentials, page, pw_timeout):
    """Test customer login flow on storefront."""
    login_url = f"{shopping_base_url}/customer/account/login"

    page.goto(login_url, timeout=pw_timeout)

    # Wait for login form
    page.wait_for_selector('input[name="login[username]"]', timeout=pw_timeout)

    # Fill in credentials
    page.fill('input[name="login[username]"]', shopping_credentials["email"])
    page.fill('input[name="login[password]"]', shopping_credentials["password"])

    # Click login button
    page.click('button[type="submit"].action.login')

    # Wait for account page to load
    page.wait_for_selector(".block-dashboard-info, .box-information", timeout=pw_timeout)

    # Verify we're on the account page
    assert "My Account" in page.content() or "Account Information" in page.content()


@pytest.mark.flaky(reruns=2)
def test_customer_account_page(shopping_container, shopping_base_url, shopping_get_logged_page, pw_timeout):
    """Test customer account page shows correct information."""
    page = shopping_get_logged_page()

    # Navigate to account page
    page.goto(f"{shopping_base_url}/customer/account/", timeout=pw_timeout)

    # Verify account information is visible
    account_info = page.locator(".box-information, .block-dashboard-info")
    expect(account_info.first).to_be_visible(timeout=pw_timeout)


# Storefront Navigation Tests


@pytest.mark.flaky(reruns=2)
def test_shopping_homepage_loads(shopping_container, shopping_base_url, shopping_get_logged_page, pw_timeout):
    """Test that homepage loads with header (logged in)."""
    page = shopping_get_logged_page()
    page.goto(shopping_base_url, timeout=pw_timeout)
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Check that the page has loaded (look for header or logo)
    header = page.locator("header.page-header")
    expect(header).to_be_visible(timeout=pw_timeout)


@pytest.mark.flaky(reruns=2)
def test_shopping_category_page_loads(shopping_container, shopping_base_url, shopping_get_logged_page, pw_timeout):
    """Test that category page loads (logged in)."""
    page = shopping_get_logged_page()
    page.goto(f"{shopping_base_url}/{TEST_CATEGORY_URL}", timeout=pw_timeout)
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Category heading should be visible
    heading = page.locator("h1.page-title span, h1.page-title")
    expect(heading.first).to_be_visible(timeout=pw_timeout)


@pytest.mark.flaky(reruns=2)
def test_shopping_product_detail_page(shopping_container, shopping_base_url, shopping_get_logged_page, pw_timeout):
    """Test product detail page loads correctly (logged in)."""
    page = shopping_get_logged_page()
    page.goto(f"{shopping_base_url}/{TEST_PRODUCT_URL}", timeout=pw_timeout)
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Verify product title is visible
    title = page.locator("h1.page-title span")
    expect(title).to_be_visible(timeout=pw_timeout)
    expect(title).to_contain_text(TEST_PRODUCT_NAME)

    # Verify price is visible
    price = page.locator(".product-info-price .price")
    expect(price).to_be_visible(timeout=pw_timeout)


# Search Tests


@pytest.mark.flaky(reruns=2)
def test_shopping_search_page_loads(shopping_container, shopping_base_url, shopping_get_logged_page, pw_timeout):
    """Test that search page loads (logged in)."""
    page = shopping_get_logged_page()
    page.goto(f"{shopping_base_url}/catalogsearch/result/?q={TEST_SEARCH_TERM}", timeout=pw_timeout)
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Search page title should be visible
    title = page.locator("h1.page-title span, .page-title-wrapper h1")
    expect(title.first).to_be_visible(timeout=pw_timeout)


# Cart Tests


@pytest.mark.flaky(reruns=2)
def test_shopping_product_has_add_to_cart(shopping_container, shopping_base_url, shopping_get_logged_page, pw_timeout):
    """Test that in-stock product page has add to cart button (logged in)."""
    page = shopping_get_logged_page()
    page.goto(f"{shopping_base_url}/{TEST_PRODUCT_URL}", timeout=pw_timeout)
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Verify product is in stock
    availability = page.locator('[data-th="Availability"], .stock.available, .availability')
    expect(availability.first).to_contain_text("In stock", timeout=pw_timeout)

    # Verify add to cart button is present (selector varies by theme)
    add_to_cart = page.locator("button.tocart, button:has-text('Add to Cart')")
    expect(add_to_cart.first).to_be_visible(timeout=pw_timeout)

    # Verify quantity input is present
    qty_input = page.locator("input#qty, input[name='qty']")
    expect(qty_input.first).to_be_visible(timeout=pw_timeout)


# Image Loading Tests

# Products from different categories to test image loading
# Format: pytest.param(product_url, category_name, id="image_N")
TEST_PRODUCTS_FOR_IMAGES = [
    pytest.param(TEST_PRODUCT_URL, "Beauty & Personal Care", id="image_1"),
    pytest.param("toolworx-precision-cut-pro-toenail-nipper.html", "Foot, Hand & Nail Care", id="image_2"),
    pytest.param(
        "hazel-nintendo-animal-crossing-happy-home-designer-amiibo-card-248.html", "Nintendo Systems", id="image_3"
    ),
    pytest.param(
        "powered-toothbrush-sets-with-your-favorite-star-wars-characters-3-piece-chewbacca.html",
        "Children's Dental Care",
        id="image_4",
    ),
    pytest.param(
        "stainless-steel-tongue-scraper-portable-freshen-breath-tongue-cleaner-oral-care-tool-tongue-scraper-stainless-steel-tongue-scraper-tongue-cleaner-freshen-breath.html",
        "Tongue Cleaners",
        id="image_5",
    ),
    pytest.param("de-chanceny-cremant-de-loire-rose-375ml.html", "Alcoholic Beverages", id="image_6"),
    pytest.param(
        "afuower-nail-polish-organizer-bag-with-handles-holds-30-bottles-15ml-0-5-fl-oz-travel-case-portable-storage-bag-for-manicure-set-pink.html",
        "Nail Art & Polish",
        id="image_7",
    ),
    pytest.param(
        "dimj-closet-organizer-storage-washable-storage-basket-for-shelves-large-closet-storage-bins-collapsible-rectangular-fabric-basket-for-clothes-toys-home-beige-grey-large.html",
        "Baskets, Bins & Containers",
        id="image_8",
    ),
    pytest.param(
        "charger-cable-for-ns-switch-and-switch-lite-2-pack-10ft-nylon-braided-usb-c-to-usb-a-type-c-fast-data-sync-power-charging-cord-accessories-for-samsung-galaxy-s9-s8-note-9-pixel-lg-v30-g6-oneplus.html",
        "Nintendo Switch",
        id="image_9",
    ),
    pytest.param(
        "emergency-solar-power-radio-with-4000mah-battery-hand-crank-survival-radio-with-flashlight-cell-phone-charger-sos-alarm-survival-whistle-for-snowstorm-hiking-picnic-camping-outdoor-activities-light.html",
        "Radios",
        id="image_10",
    ),
]


@pytest.mark.flaky(reruns=2)
@pytest.mark.parametrize(("product_url", "category"), TEST_PRODUCTS_FOR_IMAGES)
def test_product_images_load(
    shopping_container, shopping_base_url, shopping_get_logged_page, pw_timeout, product_url, category
):
    """Test that product images load correctly (not placeholders).

    Magento serves a 1692-byte placeholder image when the actual image is missing.
    This test verifies that product images are real images, not placeholders.
    """
    page = shopping_get_logged_page()
    page.goto(f"{shopping_base_url}/{product_url}", timeout=pw_timeout)
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Get all product gallery images
    images = page.locator(".product.media img, .gallery-placeholder img, .fotorama__img")
    image_count = images.count()

    assert image_count > 0, f"No product images found on page for {category}"

    # Collect image URLs (filter out data URIs and empty src)
    image_urls = []
    for i in range(image_count):
        src = images.nth(i).get_attribute("src")
        if src and src.startswith("http") and "placeholder" not in src.lower():
            image_urls.append(src)

    assert len(image_urls) > 0, f"No valid product image URLs found for {category}"

    # Verify each image is not a placeholder (check Content-Length)
    placeholder_images = []
    for url in image_urls:
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=10) as response:
                content_length = int(response.headers.get("Content-Length", 0))
                if content_length == PLACEHOLDER_IMAGE_SIZE:
                    placeholder_images.append(url)
        except Exception as e:
            placeholder_images.append(f"{url} (error: {e})")

    assert len(placeholder_images) == 0, f"Found placeholder/missing images in {category}: {placeholder_images}"

import pytest
from bs4 import BeautifulSoup
from app.scraper.google_maps.locator import PostLocator
from app.scraper.google_maps.extractor import PostExtractor
from app.scraper.google_maps.captcha import CaptchaDetector
from app.scraper.google_maps.normalizer import Normalizer
from app.scraper.google_maps.identity import IdentityGenerator

# ---------------------------------------------------------------------------
# HTML Fixtures
# ---------------------------------------------------------------------------

# 1. Normal profile with multiple posts (legacy DOM – data-post-id / role=feed)
FIXTURE_NORMAL = """
<html>
  <div role="feed">
    <div data-post-id="post-1" class="ODSEW-BN9H-post">
      <span class="ylH6lf">Oct 21, 2023</span>
      <div>
        <p>This is a normal post text. Very long so it gets detected correctly over 20 chars.</p>
      </div>
      <img src="http://example.com/img1.jpg" />
      <a href="http://example.com/cta">Learn more</a>
    </div>
    <div data-post-id="post-2" class="ODSEW-BN9H-post">
      <span class="ylH6lf">3 days ago</span>
      <div>
        <p>This is another post text. Let's make it long enough to be extracted.</p>
      </div>
      <div style="background-image: url('http://example.com/bg.jpg')"></div>
    </div>
  </div>
</html>
"""

# 2. Captcha page
FIXTURE_CAPTCHA = """
<html>
    <body>
        <div>Our systems have detected unusual traffic from your computer network.</div>
        <form id="captcha-form">
           <div class="g-recaptcha"></div>
        </form>
    </body>
</html>
"""

# 3. No posts
FIXTURE_NO_POSTS = """
<html>
  <div role="feed">
  </div>
</html>
"""

# 4. Malformed post (no ID, missing parts)
FIXTURE_MALFORMED = """
<html>
  <div role="feed">
    <div class="random-class">
      <span>Not a date</span>
      <p>Short</p>
    </div>
  </div>
</html>
"""

# 5. Current Google Maps DOM (2026) – localPostExpanded / TrG26d / TW2TI /
#    ABZ6xb / tTCrvf / data-sharing-url with lpsid
FIXTURE_CURRENT_DOM = """
<html>
  <div>
    <div class="localPostExpanded"
         data-sharing-url="https://maps.google.com/?cid=123&lpsid=CIHM0ogKEICAuIr7nZ2bFRAB">
      <div class="TrG26d">
        Try our brand-new autumn menu starting this October. Fresh ingredients, bold flavours.
      </div>
      <span class="TW2TI">3 days ago</span>
      <img class="tTCrvf" src="https://lh5.googleusercontent.com/p/post-image.jpg" />
      <a class="ABZ6xb" href="https://example.com/menu">View menu</a>
    </div>
    <div class="localPostExpanded"
         data-sharing-url="https://maps.google.com/?cid=123&lpsid=CIHM0ogKEICAuIr7nZ2bFRBB">
      <div class="TrG26d">
        We are open on all public holidays. Come visit us for a warm meal!
      </div>
      <span class="TW2TI">1 week ago</span>
      <img class="tTCrvf" src="https://lh5.googleusercontent.com/p/post-image-2.jpg" />
    </div>
  </div>
</html>
"""

# 6. data-sharing-url only (no localPostExpanded – another DOM variant)
FIXTURE_SHARING_URL_ONLY = """
<html>
  <div>
    <div data-sharing-url="https://maps.google.com/?lpsid=ABC123&cid=456">
      <div class="TrG26d">
        Post text here for the sharing-url variant. Long enough to be detected.
      </div>
      <span class="TW2TI">2 weeks ago</span>
    </div>
  </div>
</html>
"""

# 7. "From the owner" section variant
FIXTURE_FROM_THE_OWNER = """
<html>
  <div class="S3NLN">
    <div class="fontHeadlineSmall zSdcRe PiF0we">From the owner</div>
    <div class="Q7eoI">
      <div class="SBD2Rc waIsr">
        <div class="L6Bbsd"></div>
        <div class="jQnbnc fontBodyMedium LC9kbb">
          <div class="HYLSGb">
            <div class="QI7YL">
              <div class="sv3F6e fontTitleSmall">Masti, Mithai, aur P</div>
            </div>
            <div class="hzT4mb">27 Feb - 4 Feb</div>
            <div class="VpMB0 taHin">Some flavours just f</div>
          </div>
          <div class="fontBodyMedium lqMB">Feb 27, 2026</div>
          <div class="dsrqad">
            <a href="https://example.com/order">Order online</a>
          </div>
        </div>
      </div>
    </div>
  </div>
</html>
"""

# ---------------------------------------------------------------------------
# Tests – legacy DOM
# ---------------------------------------------------------------------------

def test_locator_normal():
    soup = BeautifulSoup(FIXTURE_NORMAL, "html.parser")
    containers = PostLocator.locate(soup)
    assert len(containers) == 2


def test_locator_no_posts():
    soup = BeautifulSoup(FIXTURE_NO_POSTS, "html.parser")
    containers = PostLocator.locate(soup)
    assert len(containers) == 0


def test_extractor_normal():
    soup = BeautifulSoup(FIXTURE_NORMAL, "html.parser")
    containers = PostLocator.locate(soup)

    post1 = PostExtractor.extract(containers[0])
    assert post1.source_id == "post-1"
    assert post1.text_content == "This is a normal post text. Very long so it gets detected correctly over 20 chars."
    assert post1.cta_text == "Learn more"
    assert post1.cta_url == "http://example.com/cta"
    assert "http://example.com/img1.jpg" in post1.media_urls

    post2 = PostExtractor.extract(containers[1])
    assert post2.source_id == "post-2"
    assert "http://example.com/bg.jpg" in post2.media_urls


def test_normalizer():
    soup = BeautifulSoup(FIXTURE_NORMAL, "html.parser")
    containers = PostLocator.locate(soup)
    post = PostExtractor.extract(containers[0])

    post.text_content = "This   is  a  \n\n text   "
    post.cta_text = " Learn more "

    normalized = Normalizer.normalize(post)
    assert normalized.text_content == "This is a \n text"
    assert normalized.cta_text == "Learn more"


def test_identity_generator():
    soup = BeautifulSoup(FIXTURE_NORMAL, "html.parser")
    containers = PostLocator.locate(soup)
    post = PostExtractor.extract(containers[0])
    post = Normalizer.normalize(post)

    fp = IdentityGenerator.generate_fingerprint(post)
    assert fp == "post-1"

    post.source_id = None
    fp2 = IdentityGenerator.generate_fingerprint(post)
    assert len(fp2) == 64  # SHA-256 hex digest


def test_captcha_detector():
    soup = BeautifulSoup(FIXTURE_CAPTCHA, "html.parser")
    assert CaptchaDetector.detect(soup) is True

    soup_normal = BeautifulSoup(FIXTURE_NORMAL, "html.parser")
    assert CaptchaDetector.detect(soup_normal) is False


# ---------------------------------------------------------------------------
# Tests – current Google Maps DOM (2026)
# ---------------------------------------------------------------------------

def test_locator_current_dom():
    """Locator should find posts via localPostExpanded class."""
    soup = BeautifulSoup(FIXTURE_CURRENT_DOM, "html.parser")
    containers = PostLocator.locate(soup)
    assert len(containers) == 2


def test_locator_sharing_url_only():
    """Locator should find posts via data-sharing-url when localPostExpanded is absent."""
    soup = BeautifulSoup(FIXTURE_SHARING_URL_ONLY, "html.parser")
    containers = PostLocator.locate(soup)
    assert len(containers) == 1


def test_extractor_current_dom_text():
    """Extractor should pull text from TrG26d."""
    soup = BeautifulSoup(FIXTURE_CURRENT_DOM, "html.parser")
    containers = PostLocator.locate(soup)
    post = PostExtractor.extract(containers[0])
    assert "autumn menu" in (post.text_content or "")


def test_extractor_current_dom_source_id():
    """Extractor should pull lpsid from data-sharing-url."""
    soup = BeautifulSoup(FIXTURE_CURRENT_DOM, "html.parser")
    containers = PostLocator.locate(soup)
    post = PostExtractor.extract(containers[0])
    assert post.source_id == "CIHM0ogKEICAuIr7nZ2bFRAB"


def test_extractor_current_dom_cta():
    """Extractor should pull CTA text and URL from ABZ6xb."""
    soup = BeautifulSoup(FIXTURE_CURRENT_DOM, "html.parser")
    containers = PostLocator.locate(soup)
    post = PostExtractor.extract(containers[0])
    assert post.cta_text == "View menu"
    assert post.cta_url == "https://example.com/menu"


def test_extractor_current_dom_media():
    """Extractor should find image URL from tTCrvf img tag."""
    soup = BeautifulSoup(FIXTURE_CURRENT_DOM, "html.parser")
    containers = PostLocator.locate(soup)
    post = PostExtractor.extract(containers[0])
    assert any("post-image.jpg" in url for url in post.media_urls)


def test_extractor_current_dom_date():
    """Extractor should parse date from TW2TI span."""
    soup = BeautifulSoup(FIXTURE_CURRENT_DOM, "html.parser")
    containers = PostLocator.locate(soup)
    post = PostExtractor.extract(containers[0])
    # dateparser should resolve "3 days ago" to a recent date
    assert post.published_date is not None
    assert post.published_date.year >= 2024


def test_extractor_sharing_url_lpsid():
    """Extractor should extract lpsid from data-sharing-url variant."""
    soup = BeautifulSoup(FIXTURE_SHARING_URL_ONLY, "html.parser")
    containers = PostLocator.locate(soup)
    post = PostExtractor.extract(containers[0])
    assert post.source_id == "ABC123"


def test_locator_from_the_owner():
    """Locator should find posts within the 'From the owner' section."""
    soup = BeautifulSoup(FIXTURE_FROM_THE_OWNER, "html.parser")
    containers = PostLocator.locate(soup)
    assert len(containers) == 1


def test_extractor_from_the_owner():
    """Extractor should pull text, date, and CTA from 'From the owner' structure."""
    soup = BeautifulSoup(FIXTURE_FROM_THE_OWNER, "html.parser")
    containers = PostLocator.locate(soup)
    post = PostExtractor.extract(containers[0])
    
    assert post.text_content == "Masti, Mithai, aur P 27 Feb - 4 Feb Some flavours just f"
    assert post.published_date is not None
    assert post.published_date.year == 2026
    assert post.cta_text == "Order online"
    assert post.cta_url == "https://example.com/order"


def test_full_pipeline_current_dom():
    """End-to-end: locate → extract → normalize → fingerprint."""
    soup = BeautifulSoup(FIXTURE_CURRENT_DOM, "html.parser")
    containers = PostLocator.locate(soup)
    assert len(containers) == 2

    for container in containers:
        post = PostExtractor.extract(container)
        post = Normalizer.normalize(post)
        fp = IdentityGenerator.generate_fingerprint(post)
        assert fp  # must produce a non-empty fingerprint
        assert len(fp) > 0


def test_second_post_no_cta():
    """Second post in current DOM fixture has no CTA — should return None gracefully."""
    soup = BeautifulSoup(FIXTURE_CURRENT_DOM, "html.parser")
    containers = PostLocator.locate(soup)
    post = PostExtractor.extract(containers[1])
    assert post.cta_text is None
    assert post.cta_url is None
    assert post.source_id == "CIHM0ogKEICAuIr7nZ2bFRBB"

import pytest
from bs4 import BeautifulSoup
from app.scraper.google_maps.locator import PostLocator
from app.scraper.google_maps.extractor import PostExtractor
from app.scraper.google_maps.captcha import CaptchaDetector
from app.scraper.google_maps.normalizer import Normalizer
from app.scraper.google_maps.identity import IdentityGenerator

# 1. Normal profile with multiple posts
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


def test_locator_normal():
    soup = BeautifulSoup(FIXTURE_NORMAL, 'html.parser')
    containers = PostLocator.locate(soup)
    assert len(containers) == 2

def test_locator_no_posts():
    soup = BeautifulSoup(FIXTURE_NO_POSTS, 'html.parser')
    containers = PostLocator.locate(soup)
    assert len(containers) == 0

def test_extractor_normal():
    soup = BeautifulSoup(FIXTURE_NORMAL, 'html.parser')
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
    soup = BeautifulSoup(FIXTURE_NORMAL, 'html.parser')
    containers = PostLocator.locate(soup)
    post = PostExtractor.extract(containers[0])
    
    # Mess it up
    post.text_content = "This   is  a  \n\n text   "
    post.cta_text = " Learn more "
    
    normalized = Normalizer.normalize(post)
    assert normalized.text_content == "This is a \n text"
    assert normalized.cta_text == "Learn more"

def test_identity_generator():
    soup = BeautifulSoup(FIXTURE_NORMAL, 'html.parser')
    containers = PostLocator.locate(soup)
    post = PostExtractor.extract(containers[0])
    post = Normalizer.normalize(post)
    
    # When source_id is present, it should use it
    fp = IdentityGenerator.generate_fingerprint(post)
    assert fp == "post-1"
    
    # Without source_id, it should generate a hash
    post.source_id = None
    fp2 = IdentityGenerator.generate_fingerprint(post)
    assert len(fp2) == 64 # SHA256

def test_captcha_detector():
    soup = BeautifulSoup(FIXTURE_CAPTCHA, 'html.parser')
    assert CaptchaDetector.detect(soup) == True
    
    soup_normal = BeautifulSoup(FIXTURE_NORMAL, 'html.parser')
    assert CaptchaDetector.detect(soup_normal) == False

import asyncio
import os
from random import randrange
from typing import Literal
from pydoll.browser.tab import Tab
from pydoll.elements.web_element import WebElement
from pydoll.exceptions import WaitElementTimeout, ElementNotFound
import pydub
import speech_recognition
import urllib
from smart_apply.browser_utils import script_value
from smart_apply.logger import log_info
from smart_apply.result import Err, Ok, Result, safe_fn


async def page_has_recaptcha(tab: Tab) -> bool:
    """Detect if ReCaptcha is present on the page."""
    markers = ['grecaptcha', 'recaptcha/api.js', 'recaptcha__', 'g-recaptcha']
    content = await tab.page_source
    return any(m in content for m in markers)


async def recaptcha_within_container(container: WebElement) -> bool:
    """Check if a visible ReCaptcha V2 is present in the given container.
    Args:
        container (WebElement): The container to search within (usually a form).
    """
    try:
        iframe = await container.query('iframe[src*="recaptcha"]', timeout=15)
       
        if not iframe:
            return False
        
        # TODO: is this line needed?
        await iframe.wait_until(is_visible=True, timeout=15)

         # Check if it's visible v2 recaptcha with checkbox (not invisible or v3)
        await iframe.query('.recaptcha-checkbox-checkmark')

        return True
    except (WaitElementTimeout, ElementNotFound):
        return False


@safe_fn
async def solve_recaptcha_if_present(container: WebElement, tab: Tab) -> Result[Literal['not_detected', 'solved'], Exception]:
    recaptcha_signs_detected = await page_has_recaptcha(tab)
    recaptcha = await recaptcha_within_container(container) if recaptcha_signs_detected else None

    if not recaptcha:
        return Ok('not_detected')

    try:
        await solve_recaptcha(tab)
    except Exception as e:
        return Err(e)

    return Ok('solved')


# Constants
TEMP_DIR = os.getenv("TEMP") if os.name == "nt" else "/tmp"
TIMEOUT_STANDARD = 7
TIMEOUT_SHORT = 1
TIMEOUT_DETECTION = 0.05


async def solve_recaptcha(tab: Tab) -> None:
    """Attempt to solve the reCAPTCHA challenge via checkbox click,
    falling back to audio recognition if needed.

    Raises:
        RuntimeError: If captcha solving fails or bot is detected.
    """
    # Find and click the reCAPTCHA checkbox iframe
    checkbox_iframe = await tab.query(
        'iframe[title="reCAPTCHA"]', timeout=TIMEOUT_STANDARD
    )
    await checkbox_iframe.wait_until(is_visible=True, timeout=TIMEOUT_STANDARD)
    await asyncio.sleep(0.1)

    content = await checkbox_iframe.query(
        '.rc-anchor-content', timeout=TIMEOUT_STANDARD
    )
    log_info('Clicking on ReCaptcha checkbox.')
    await content.click()

    # Check if solved by just clicking
    if await recaptcha_solved(tab):
        log_info('ReCaptcha solved via checkbox click.')
        return

    # Handle audio challenge
    challenge_iframe = await tab.query(
        'iframe[title*="recaptcha challenge"]', timeout=TIMEOUT_STANDARD
    )
    audio_btn = await challenge_iframe.query(
        '#recaptcha-audio-button', timeout=TIMEOUT_STANDARD
    )
    await audio_btn.click()
    await asyncio.sleep(0.3)

    if await recaptcha_detected_bot(tab):
        raise RuntimeError('Captcha detected bot behavior')

    # Download and process audio
    audio_source = await challenge_iframe.query(
        '#audio-source', timeout=TIMEOUT_STANDARD
    )
    src_result = await audio_source.execute_script(
        'return this.src', return_by_value=True
    )
    src = script_value(src_result)

    try:
        text_response = await asyncio.to_thread(recognize_audio_challenge, src)

        response_input = await challenge_iframe.query('#audio-response')
        await response_input.insert_text(text_response.lower())

        verify_btn = await challenge_iframe.query('#recaptcha-verify-button')
        await verify_btn.click()
        await asyncio.sleep(0.4)

        if not await recaptcha_solved(tab):
            raise RuntimeError('Failed to solve the captcha')

        log_info('ReCaptcha solved via audio challenge.')

    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f'Audio challenge failed: {e}') from e


def recognize_audio_challenge(audio_url: str) -> str:
    """Download the audio challenge, convert to WAV, and return recognized text.

    This is intentionally synchronous (file I/O + speech recognition).
    Call via ``asyncio.to_thread`` to avoid blocking the event loop.
    """
    mp3_path = os.path.join(TEMP_DIR, f'{randrange(1, 1000)}.mp3')
    wav_path = os.path.join(TEMP_DIR, f'{randrange(1, 1000)}.wav')

    try:
        urllib.request.urlretrieve(audio_url, mp3_path)
        sound = pydub.AudioSegment.from_mp3(mp3_path)
        sound.export(wav_path, format='wav')

        recognizer = speech_recognition.Recognizer()
        with speech_recognition.AudioFile(wav_path) as source:
            audio = recognizer.record(source)

        return recognizer.recognize_google(audio)

    finally:
        for path in (mp3_path, wav_path):
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass


async def recaptcha_solved(tab: Tab) -> bool:
    """Check if the reCAPTCHA has been solved successfully."""
    try:
        checkbox_iframe = await tab.query(
            'iframe[title="reCAPTCHA"]', raise_exc=False
        )
        if not checkbox_iframe:
            return False
        checkmark = await checkbox_iframe.query(
            '.recaptcha-checkbox-checkmark', raise_exc=False
        )
        if not checkmark:
            return False
        result = await checkmark.execute_script(
            "return this.hasAttribute('style')", return_by_value=True
        )
        return bool(script_value(result))
    except Exception:
        return False


async def recaptcha_detected_bot(tab: Tab) -> bool:
    """Check if the bot has been detected by reCAPTCHA."""
    try:
        challenge_iframe = await tab.query(
            'iframe[title*="recaptcha challenge"]', raise_exc=False
        )
        if not challenge_iframe:
            return False
        el = await challenge_iframe.query(
            '.rc-doscaptcha-header-text', raise_exc=False
        )
        if not el:
            return False
        return await el.is_visible()
    except Exception:
        return False


async def recaptcha_response_token(tab: Tab) -> str | None:
    """Get the reCAPTCHA response token if available."""
    try:
        el = await tab.query('#recaptcha-token', raise_exc=False)
        if not el:
            return None
        result = await el.execute_script(
            'return this.value', return_by_value=True
        )
        return script_value(result) or None
    except Exception:
        return None
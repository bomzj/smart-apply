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


async def find_recaptcha(container: WebElement) -> WebElement | None:
    """Check if a visible ReCaptcha V2 is present in the given container.
    Args:
        container (WebElement): The container to search within (usually a form).
    """
    try:
        iframe = await container.query('iframe[src*="recaptcha"]', timeout=15)
       
        if not iframe:
            return None
        
        # TODO: is this line needed?
        await iframe.wait_until(is_visible=True, timeout=15)

         # Check if it's visible v2 recaptcha with checkbox (not invisible or v3)
        await iframe.query('.recaptcha-checkbox-checkmark')

        return iframe
    except (WaitElementTimeout, ElementNotFound):
        return None


@safe_fn
async def solve_recaptcha_if_present(container: WebElement, tab: Tab) -> Result[Literal['not_detected', 'solved'], Exception]:
    recaptcha_signs_detected = await page_has_recaptcha(tab)
    recaptcha = await find_recaptcha(container) if recaptcha_signs_detected else None

    if not recaptcha:
        return Ok('not_detected')

    try:
        await recaptcha.scroll_into_view()
        await solve_recaptcha(tab)
    except Exception as e:
        return Err(e)

    return Ok('solved')


# Constants
TEMP_DIR = os.getenv("TEMP") if os.name == "nt" else "/tmp"
TIMEOUT_STANDARD = 7


async def solve_recaptcha(tab: Tab) -> None:
    """Attempt to solve the reCAPTCHA challenge via checkbox click,
    falling back to audio recognition if needed.

    Raises:
        RuntimeError: If captcha solving fails or bot is detected.
    """
    # HACK: Pydoll has issues with recaptcha iframe(or iframes at all) and wrongly clicks on its elements inside
    # https://github.com/autoscrape-labs/pydoll/issues/370
    # every time we use the iframe element, we need to re-query it to get a fresh reference that works correctly
    async def checkbox_iframe():
        return await tab.query(
            'iframe[title="reCAPTCHA"]', timeout=TIMEOUT_STANDARD
        )
    
    async def challenge_iframe():
        return await tab.query(
            'iframe[title*="recaptcha challenge"]', timeout=TIMEOUT_STANDARD
        )
    
    # Find and click the reCAPTCHA checkbox iframe
    await (await checkbox_iframe()).click()

    # Check if solved by just clicking
    if await recaptcha_solved(tab):
        return

    # Handle audio challenge
    bounds = await (await challenge_iframe()).bounds
    audio_btn = await (await challenge_iframe()).query(
        '#recaptcha-audio-button', timeout=TIMEOUT_STANDARD
    )
    await audio_btn.click(x_offset=bounds[0], y_offset=bounds[1])

    if await recaptcha_detected_bot(tab):
        raise RuntimeError('ReCaptcha detected bot behavior')

    # Download and process audio
    audio_source = await (await challenge_iframe()).query(
        '#audio-source', timeout=TIMEOUT_STANDARD
    )
    src_result = await audio_source.execute_script(
        'return this.src', return_by_value=True
    )
    src = script_value(src_result)

    try:
        text_response = await asyncio.to_thread(recognize_text_from_audio, src)

        # Insert the recognized text
        response_input = await (await challenge_iframe()).query('#audio-response')
        await response_input.insert_text(text_response.lower())

        # Click the verify button
        bounds = await (await challenge_iframe()).bounds
        verify_btn = await (await challenge_iframe()).query('#recaptcha-verify-button')
        await verify_btn.click(x_offset=bounds[0], y_offset=bounds[1])

        if not await recaptcha_solved(tab):
            raise RuntimeError('Failed to solve the ReCaptcha')

        #log_debug('ReCaptcha solved via audio challenge')

    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f'Audio challenge failed: {e}') from e


def recognize_text_from_audio(audio_url: str) -> str:
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
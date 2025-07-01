"""Simplified gradio demo server for Music Arena."""

import argparse
import functools
import logging
import pathlib
import random
import time
from typing import Optional

import gradio as gr

from music_arena.dataclass import (
    Battle,
    ListenEvent,
    Preference,
    Session,
    SimpleTextToMusicPrompt,
    SystemKey,
    User,
    Vote,
)
from music_arena.exceptions import PromptContentException, SystemTimeoutException
from music_arena.helper import salted_checksum
from music_arena.logging import get_battle_logger
from music_arena.secret import get_secret

from . import constants as C
from . import gateway as G
from . import js as J

_LOGGER = logging.getLogger(__name__)
_LOGGER.info(f"Using BACKEND_URL={G.URL}")

STATIC_DIR = pathlib.Path(__file__).parent / "static"


# Helpers


def load_static_file(name: str) -> str:
    with open(STATIC_DIR / name, "r") as f:
        return f.read()


def get_ip(request: gr.Request) -> Optional[str]:
    """Extract IP address from request"""
    if "cf-connecting-ip" in request.headers:
        return request.headers["cf-connecting-ip"]
    elif "x-forwarded-for" in request.headers:
        ip = request.headers["x-forwarded-for"]
        return ip.split(",")[0] if "," in ip else ip
    return request.client.host


def render_model_description(systems) -> str:
    if not systems or len(systems) == 0:
        return C.MODEL_DESCRIPTION_UNAVAILABLE_MD

    # Create table header
    md = "| Display Name | Organization | Access | Lyrics | Link | Description |\n"
    md += "|---|---|---|---|---|---|\n"

    for _, system in systems.items():
        # Extract values from System object, handling None values
        display_name = system.display_name or system.tag
        organization = system.organization or "-"
        access = system.access.value or "-"
        lyrics = "✓" if system.supports_lyrics else "✗"
        link = f"[Link]({system.primary_link})" if system.primary_link else "-"
        description = system.description or C.MODEL_DESCRIPTION_NO_AVAILABLE

        # Add row to table
        md += f"| {display_name} | {organization} | {access} | {lyrics} | {link} | {description} |\n"

    return md


def set_visible(session, criteria, name, negate, num_elements):
    logger = get_battle_logger("set_visible", session=session)
    if negate:
        criteria = not criteria
    logger.info(f"name={name}, criteria={criteria}, num_elements={num_elements}")
    if num_elements == 1:
        return gr.update(visible=criteria)
    else:
        return [gr.update(visible=criteria) for _ in range(num_elements)]


# Setup callbacks


def onload_init_session():
    session = Session()
    logger = get_battle_logger("onload_init_session", session=session)
    logger.info(f"Initialized session={session}")
    return session


def onsession_raise_for_no_tos_cookie(session, request: gr.Request):
    """Return True if TOS cookie is set, otherwise raise an error"""
    assert session is not None
    logger = get_battle_logger("onsession_raise_for_no_tos_cookie", session=session)
    tos_cookie = request.headers.get("cookie", "")
    tos_cookie_name = "tos_accepted_" + C.TERMS_CHECKSUM
    found = tos_cookie_name in tos_cookie
    logger.info(
        f"found={found}, tos_cookie_name={tos_cookie_name}, tos_cookie={tos_cookie}"
    )
    if not found:
        raise Exception("TOS not previously accepted, require manual.")


def onack_init_user(session, request: gr.Request):
    """Track salted IP and browser fingerprint as a form of anonymous user tracking"""
    # This anonymous tracking method only called if TOS is accepted
    assert session.ack_tos == C.TERMS_CHECKSUM

    logger = get_battle_logger("onack_init_user", session=session)
    logger.info("Creating user")
    salt = get_secret("ANONYMIZED_USER_SALT", randomly_initialize=True)

    # Get salted IP
    try:
        salted_ip = salted_checksum(get_ip(request), salt)
    except Exception as e:
        logger.error(f"Error in onload_anonymous_user_tracking: {e}")
        salted_ip = None

    # TODO: Get salted browser fingerprint

    # Create user
    user = User(salted_ip=salted_ip)
    logger = get_battle_logger("onack_init_user", session=session, user=user)
    logger.info(f"Created user={user}")
    return user


def onack_fetch_from_gateway(session):
    """Load systems and prebaked prompts from gateway."""
    assert session is not None
    logger = get_battle_logger("onack_fetch_systems_and_prebaked", session=session)
    systems = G.get_systems()
    logger.info(f"len_systems={len(systems)}")
    prebaked = G.get_prebaked_prompts()
    logger.info(f"len_prebaked={len(prebaked)}")
    return systems, prebaked


def ongateway_update_ui(session, systems, prebaked):
    """Update UI based on gateway status"""
    assert all(x is not None for x in [session, systems, prebaked])
    logger = get_battle_logger("onfetch_update_ui", session=session)
    prebaked_ready = len(prebaked) > 0
    logger.info(f"prebaked_ready={prebaked_ready},")
    return (
        render_model_description(systems),
        gr.update(visible=prebaked_ready),
        gr.update(scale=7 if prebaked_ready else 9),
        gr.update(visible=prebaked_ready),
    )


# Callbacks for specific input elements


def handle_prebake_btn_click(prebaked):
    """Handle prebake button click - generate lyrics"""
    prompt = random.choice(list(prebaked.values()))
    return [prompt.overall_prompt, prompt]


# Shared callbacks for several input elements


def handle_new_battle(session, user, debug=False):
    assert session is not None and user is not None
    logger = get_battle_logger("handle_new_battle", session=session, user=user)
    new_battle_times = session.new_battle_times + [time.time()]
    logger.info(f"new_battle_times={new_battle_times}")
    return [
        # STATE
        session.copy(new_battle_times=new_battle_times),  # session
        Battle(),  # battle
        None,  # vote
        False,  # voting_enabled
        # UI (same as default values when UI is created)
        gr.update(value="", visible=False),  # battle_uuid
        gr.update(show_download_button=False),  # a_music_player
        gr.update(show_download_button=False),  # b_music_player
        gr.update(value="", visible=False),  # a_lyrics
        gr.update(value="", visible=False),  # b_lyrics
        gr.update(value=C.HIDDEN_TAG_LABEL, visible=False),  # a_system_tag
        gr.update(value=C.HIDDEN_TAG_LABEL, visible=False),  # b_system_tag
        gr.update(
            value=C.VOTE_ALLOWED_MSG if debug else C.VOTE_NOT_ALLOWED_MSG, visible=debug
        ),  # vote_status_markdown
        gr.update(visible=debug, interactive=False, variant="primary"),  # vote_a_btn
        gr.update(visible=debug, interactive=False, variant="primary"),  # vote_b_btn
        gr.update(
            visible=debug, interactive=False, variant="secondary"
        ),  # vote_tie_btn
        gr.update(
            visible=debug, interactive=False, variant="secondary"
        ),  # vote_both_bad_btn
        gr.update(visible=False),  # download_file
        gr.update(visible=debug),  # new_round_btn
        gr.update(visible=debug),  # regenerate_btn
    ]


def record_audio_event(vote, name, event):
    key = f"{name}_listen_data"
    listen_data = getattr(vote, key)
    return vote.copy(**{key: listen_data + [(event, time.time())]})


def handle_generate(session, user, raw_prompt, detailed_prompt, debug=False):
    """Handle generate button click"""
    assert (
        session is not None and user is not None and session.ack_tos == C.TERMS_CHECKSUM
    )

    # Check that user has entered a prompt
    if raw_prompt is None or len(raw_prompt.strip()) == 0:
        raise gr.Error("Please enter a prompt")

    # Only use the hidden detailed prompt if it matches the visible simple prompt
    if detailed_prompt is not None and detailed_prompt.overall_prompt == raw_prompt:
        prompt = None
    else:
        prompt = SimpleTextToMusicPrompt.from_text(raw_prompt)
        detailed_prompt = None

    # Call backend
    logger = get_battle_logger("handle_generate", session=session, user=user)
    logger.info(f"raw_prompt={raw_prompt}, detailed_prompt={detailed_prompt}")
    try:
        battle = G.post_generate_battle(
            session=session,
            user=user,
            prompt=prompt,
            detailed_prompt=detailed_prompt,
        )
    except PromptContentException as e:
        raise gr.Error(
            C.RATIONALE_TO_ERROR_MSG.get(e.rationale, C.UNKNOWN_RATIONALE_ERROR_MSG)
        ) from e
    except SystemTimeoutException as e:
        raise gr.Error(C.GATEWAY_TIMEOUT_MSG) from e
    except Exception as e:
        raise gr.Error(C.GATEWAY_UNAVAILABLE_MSG) from e
    logger = get_battle_logger(
        "handle_generate", session=session, user=user, battle=battle
    )
    logger.info(f"routed_prompt={battle.prompt_detailed}")

    assert (
        battle.a_audio_url is not None
        and battle.b_audio_url is not None
        and battle.prompt_detailed is not None
        and battle.a_metadata.system_key is None
        and battle.b_metadata.system_key is None
        and battle.vote is None
    )

    # Parse result
    if battle.prompt_detailed.generate_lyrics:
        generated_lyrics = [
            C.LYRICS_A_LABEL + battle.a_metadata.lyrics,
            C.LYRICS_B_LABEL + battle.b_metadata.lyrics,
        ]
    else:
        generated_lyrics = ["", ""]

    return [
        # STATE
        battle,
        Vote(),
        battle.prompt_detailed,
        # UI
        gr.update(
            value=f"{C.BATTLE_UUID_LABEL}{battle.uuid}", visible=True
        ),  # (UI) battle_uuid
        *(
            gr.update(value=b) for b in [battle.a_audio_url, battle.b_audio_url]
        ),  # a_music_player, b_music_player
        *[
            gr.update(value=l, visible=battle.prompt_detailed.generate_lyrics)
            for l in generated_lyrics
        ],  # a_lyrics, b_lyrics
        gr.update(value=C.VOTE_NOT_ALLOWED_MSG, visible=True),  # vote_status_markdown
        *[gr.update(visible=True)] * 4,  # vote_*_btn
    ]


def handle_maybe_enable_vote_ui(
    session,
    user,
    vote,
    voting_already_enabled,
    debug: bool = False,
):
    logger = get_battle_logger(
        "handle_maybe_enable_vote_ui", session=session, user=user
    )
    if voting_already_enabled:
        return [
            True,  # voting_enabled
            *[gr.update()] * 5,  # vote_*_btn, vote_status_markdown
        ]
    else:
        a_listen_time = vote.a_listen_time
        b_listen_time = vote.b_listen_time
        a_sufficient = a_listen_time >= C.MINIMUM_LISTEN_TIME
        b_sufficient = b_listen_time >= C.MINIMUM_LISTEN_TIME
        logger.info(
            f"a_listen_time={a_listen_time:.2f}, "
            f"b_listen_time={b_listen_time:.2f}, "
        )
        if debug or (a_sufficient and b_sufficient):
            logger.info(f"Enabling voting")
            return [
                True,  # voting_enabled
                *[gr.update(interactive=True)] * 4,  # vote_*_btn
                gr.update(value=C.VOTE_ALLOWED_MSG),  # vote_status_markdown
            ]
        else:
            logger.info(f"Not enabling voting")
            # Update the UI to show the time remaining
            if a_sufficient:
                template = C.VOTE_NOT_ALLOWED_B_TEMPLATE
            elif b_sufficient:
                template = C.VOTE_NOT_ALLOWED_A_TEMPLATE
            else:
                template = C.VOTE_NOT_ALLOWED_BOTH_TEMPLATE
            template_msg = template.format(
                a_listen_time=a_listen_time, b_listen_time=b_listen_time
            )
            msg = f"{C.VOTE_NOT_ALLOWED_MSG} {template_msg}"
            return [
                False,
                *[gr.update()] * 4,  # vote_*_btn
                gr.update(value=msg),  # vote_status_markdown
            ]


def handle_vote(session, user, battle, vote, debug=False):
    """Handle vote button click - record vote"""
    assert (
        session is not None and user is not None and session.ack_tos == C.TERMS_CHECKSUM
    )
    logger = get_battle_logger("handle_vote", session=session, user=user, battle=battle)

    logger.info(
        f"a_listen_time={vote.a_listen_time:.2f}, "
        f"b_listen_time={vote.b_listen_time:.2f}, "
        f"preference={vote.preference}, "
        f"preference_time={vote.preference_time:.2f}, "
    )

    # Record vote on backend
    result = None
    try:
        result = G.post_record_vote(
            session=session,
            user=user,
            battle_uuid=battle.uuid,
            vote=vote,
        )
        logger.info(f"Recorded vote: {result}")
    except SystemTimeoutException as e:
        raise gr.Error(C.GATEWAY_TIMEOUT_MSG) from e
    except Exception as e:
        raise gr.Error(C.GATEWAY_UNAVAILABLE_MSG) from e

    return battle.copy(
        a_metadata=battle.a_metadata.copy(
            system_key=SystemKey.from_json_dict(result["system_keys"][0]),
        ),
        b_metadata=battle.b_metadata.copy(
            system_key=SystemKey.from_json_dict(result["system_keys"][1]),
        ),
    )


def handle_vote_success(session, user, battle, vote, systems):
    """Handle successful vote recording - update UI"""
    logger = get_battle_logger(
        "handle_vote_success", session=session, user=user, battle=battle
    )

    # Prepare system labels
    system_keys = [battle.a_metadata.system_key, battle.b_metadata.system_key]
    system_names = []
    system_labels_md = []
    for label, key in zip([C.SYSTEM_A_LABEL, C.SYSTEM_B_LABEL], system_keys):
        if key in systems:
            name = systems[key].display_name
        else:
            name = C.SYSTEM_UNKNOWN_NAME
        system_names.append(name)
        system_labels_md.append(
            C.SYSTEM_LABEL_TEMPLATE.format(label=label, name=name, tag=key.system_tag)
        )

    # Prepare vote cast message
    vote_status_md = C.PREFERENCE_TO_VOTE_CAST_MSG[vote.preference].format(
        a_name=system_names[0],
        b_name=system_names[1],
    )

    download_url = None
    if vote.preference == Preference.A:
        download_url = battle.a_audio_url
    elif vote.preference == Preference.B:
        download_url = battle.b_audio_url

    return [
        # STATE
        battle.copy(vote=vote),
        # UI
        gr.update(
            show_download_button=True
        ),  # a_music_player OR b_music_player OR dummy
        *[
            gr.update(value=md, visible=True) for md in system_labels_md
        ],  # a_system_tag, b_system_tag
        gr.update(variant="primary"),  # *clicked* vote_*_btn
        *[gr.update(interactive=False)] * 4,  # *all* vote_*_btns
        gr.update(value=vote_status_md, visible=True),  # vote_status_markdown
        gr.update(
            value=download_url, visible=download_url is not None
        ),  # download_file
        *[gr.update(visible=True)] * 2,  # new_round_btn, regenerate_btn
    ]


# Initial demo setup


def bind_ui_events(ui, state, debug=False):
    """Bind all event handlers for the arena interface"""
    # Shorthands
    u = ui
    s = state

    # Element collections
    vote_btns = [
        u["battle"]["vote_a_btn"],
        u["battle"]["vote_b_btn"],
        u["battle"]["vote_tie_btn"],
        u["battle"]["vote_both_bad_btn"],
    ]
    generate_outputs = [
        # STATE
        s["battle"],
        s["vote"],
        s["detailed_prompt"],
        # UI
        u["battle"]["battle_uuid"],
        u["battle"]["a_music_player"],
        u["battle"]["b_music_player"],
        u["battle"]["a_lyrics"],
        u["battle"]["b_lyrics"],
        u["battle"]["vote_status_markdown"],
    ] + vote_btns
    handle_new_battle_outputs = [
        s["session"],
        s["battle"],
        s["vote"],
        s["frontend"]["voting_enabled"],
        *u["new_battle"],
    ]

    # Prebake button
    u["battle"]["prebake_btn"].click(
        fn=handle_prebake_btn_click,
        inputs=s["prebaked"],
        outputs=[
            u["battle"]["prompt_textbox"],
            s["detailed_prompt"],
        ],
    )

    # Generate button
    u["battle"]["generate_btn"].click(
        fn=functools.partial(handle_new_battle, debug=debug),
        inputs=[s["session"], s["user"]],
        outputs=handle_new_battle_outputs,
    ).then(
        fn=functools.partial(handle_generate, debug=debug),
        inputs=[
            s["session"],
            s["user"],
            u["battle"]["prompt_textbox"],
            s["detailed_prompt"],
        ],
        outputs=generate_outputs,
    )

    # Audio transport events
    for name in ["a", "b"]:
        player = u["battle"][f"{name}_music_player"]
        player.play(
            fn=functools.partial(record_audio_event, name=name, event=ListenEvent.PLAY),
            inputs=[s["vote"]],
            outputs=[s["vote"]],
        )
        player.pause(
            fn=functools.partial(
                record_audio_event, name=name, event=ListenEvent.PAUSE
            ),
            inputs=[s["vote"]],
            outputs=[s["vote"]],
        ).then(
            fn=functools.partial(handle_maybe_enable_vote_ui, debug=debug),
            inputs=[
                s["session"],
                s["user"],
                s["vote"],
                s["frontend"]["voting_enabled"],
            ],
            outputs=[
                s["frontend"]["voting_enabled"],
                *vote_btns,
                u["battle"]["vote_status_markdown"],
            ],
        )
        # TODO: Bind more player events? Stop?

    # Vote buttons
    for btn, pref in zip(
        vote_btns, [Preference.A, Preference.B, Preference.TIE, Preference.BOTH_BAD]
    ):
        if pref == Preference.A:
            winner_player = u["battle"]["a_music_player"]
        elif pref == Preference.B:
            winner_player = u["battle"]["b_music_player"]
        else:
            winner_player = gr.Audio(visible=False)  # dummy
        btn.click(
            fn=lambda vote_state, p: vote_state.copy(
                preference=p, preference_time=time.time()
            ),
            inputs=[s["vote"], gr.State(pref)],
            outputs=[s["vote"]],
        ).then(
            fn=functools.partial(handle_vote, debug=debug),
            inputs=[s["session"], s["user"], s["battle"], s["vote"]],
            outputs=[s["battle"]],
        ).success(
            fn=handle_vote_success,
            inputs=[s["session"], s["user"], s["battle"], s["vote"], s["systems"]],
            outputs=[
                s["battle"],
                winner_player,
                u["battle"]["a_system_tag"],
                u["battle"]["b_system_tag"],
                btn,
                *vote_btns,
                u["battle"]["vote_status_markdown"],
                u["battle"]["download_file"],
                u["battle"]["new_round_btn"],
                u["battle"]["regenerate_btn"],
            ],
        )

    # New round button
    u["battle"]["new_round_btn"].click(
        fn=functools.partial(handle_new_battle, debug=debug),
        inputs=[s["session"], s["user"]],
        outputs=handle_new_battle_outputs,
    ).then(
        fn=lambda: gr.update(value="", visible=True),  # prompt_textbox
        outputs=[u["battle"]["prompt_textbox"]],
    )

    # Regenerate (with same prompt) button
    u["battle"]["regenerate_btn"].click(
        fn=lambda p: p.overall_prompt,
        inputs=[s["detailed_prompt"]],
        outputs=[u["battle"]["prompt_textbox"]],
    ).then(
        fn=functools.partial(handle_new_battle, debug=debug),
        inputs=[s["session"], s["user"]],
        outputs=handle_new_battle_outputs,
    ).then(
        fn=functools.partial(handle_generate, debug=debug),
        inputs=[
            s["session"],
            s["user"],
            u["battle"]["prompt_textbox"],
            s["detailed_prompt"],
        ],
        outputs=generate_outputs,
    )


def bind_onload_events(demo, state, ui, debug=False):
    _LOGGER.info("Setting up onload handlers")

    # Shorthands
    s = state
    u = ui

    # Create new session
    onsession = demo.load(
        onload_init_session,
        outputs=s["session"],
    )

    # Shorthands for final UI visibility handler
    def set_ui_visible_kwargs(name, elems, condition, negate=False):
        return {
            "fn": functools.partial(
                set_visible, name=name, negate=negate, num_elements=len(elems)
            ),
            "inputs": [s["session"], condition],
            "outputs": elems[0] if len(elems) == 1 else elems,
        }

    def _onack_subchain(event, tos_source):
        # Chain breaks if TOS is not accepted
        onfetch = (
            event.success(
                fn=lambda x, y: x.copy(ack_tos=y),
                inputs=[s["session"], gr.State(C.TERMS_CHECKSUM)],
                outputs=[s["session"]],
            )
            .success(
                **set_ui_visible_kwargs(
                    "tos",
                    u["tos"]["rows"] + u["no_ack"]["rows"],
                    gr.State(False),
                ),
            )
            .success(
                onack_init_user,
                inputs=[s["session"]],
                outputs=[s["user"]],
            )
            .success(
                onack_fetch_from_gateway,
                inputs=[s["session"]],
                outputs=[s["systems"], s["prebaked"]],
            )
        )

        # Displays error if gateway fails to load
        gateway_success = gr.State(None)
        onfetch.then(
            fn=lambda s, p: s is not None and p is not None,
            inputs=[s["systems"], s["prebaked"]],
            outputs=[gateway_success],
        ).then(
            **set_ui_visible_kwargs(
                "no_gateway", u["no_gateway"]["rows"], gateway_success, negate=True
            ),
        )

        # Otherwise, update UI and start new battle
        onfetch.success(
            ongateway_update_ui,
            inputs=[s["session"], s["systems"], s["prebaked"]],
            outputs=[
                u["battle"]["model_description_markdown"],
                u["battle"]["prebake_btn"],
                u["battle"]["prompt_textbox_col"],
                u["battle"]["prebake_btn_col"],
            ],
        ).success(
            functools.partial(handle_new_battle, debug=debug),
            inputs=[s["session"], s["user"]],
            outputs=[
                s["session"],
                s["battle"],
                s["vote"],
                s["frontend"]["voting_enabled"],
                *u["new_battle"],
            ],
        ).success(
            **set_ui_visible_kwargs("battle", u["battle"]["rows"], gr.State(True)),
        )

    # TOS handlers
    if debug:
        _onack_subchain(onsession, gr.State("debug"))
    else:
        # Check for stored TOS acceptance on demo load
        # Will fire exception (and thus break chain) if TOS cookie not found
        check_browser_tos = onsession.success(
            fn=onsession_raise_for_no_tos_cookie,
            inputs=[s["session"]],
        )
        _onack_subchain(check_browser_tos, gr.State("browser"))

        # Manual accept button with cookie storage
        manual_accept_tos = u["tos"]["accept_btn"].click(
            fn=lambda: None,
            js=J.TOS_SET_COOKIE(C.TERMS_CHECKSUM, C.TOS_EXPIRY_HOURS),
        )
        _onack_subchain(manual_accept_tos, gr.State("manual"))

        # Manual reject button with cookie clearing
        u["tos"]["reject_btn"].click(
            **set_ui_visible_kwargs("no_ack", u["no_ack"]["rows"], gr.State(True)),
            js=J.TOS_CLEAR_COOKIE(C.TERMS_CHECKSUM),
        )


def build_ui_tos(debug=False):
    """Create and return all UI components for the terms of service modal"""
    with gr.Row() as row_terms_of_service:
        gr.Markdown(C.TERMS_OF_SERVICE_MODAL_MD, elem_id="terms-of-service-markdown")
    with gr.Row() as row_terms_of_service_buttons:
        accept_btn = gr.Button(
            value=C.TOS_ACCEPT_BUTTON_LABEL,
            elem_id="terms-of-service-accept-btn",
            variant="primary",
        )
        reject_btn = gr.Button(
            value=C.TOS_REJECT_BUTTON_LABEL,
            elem_id="terms-of-service-reject-btn",
            variant="secondary",
        )
    return {
        "rows": [row_terms_of_service, row_terms_of_service_buttons],
        "accept_btn": accept_btn,
        "reject_btn": reject_btn,
    }


def build_ui_battle(debug=False):
    """Create and return all UI components for the arena interface"""
    # Info section
    with gr.Row(visible=False) as row_info:
        with gr.Accordion(
            C.EXPAND_INFO_ACCORDION_TEXT,
            open=False,
            elem_id="info-accordion",
        ):
            gr.Markdown(C.ARENA_ABOUT_MD, elem_id="about-markdown")
            model_description_markdown = gr.Markdown(
                "", elem_id="model-description-markdown"
            )

    # Input
    with gr.Row(visible=False) as row_input:
        # Prompt textbox
        with gr.Column(scale=7, min_width=120) as prompt_textbox_col:
            prompt_textbox = gr.Textbox(
                container=False,
                show_label=False,
                placeholder=C.INPUT_PLACEHOLDER,
                elem_id="prompt-textbox",
            )

        # Prebake button
        with gr.Column(scale=2, min_width=120) as prebake_btn_col:
            prebake_btn = gr.Button(
                value=C.PREBAKE_BUTTON_LABEL,
                visible=False,
                interactive=True,
                variant="secondary",
                elem_id="prebake-btn",
            )

        # Generate button
        with gr.Column(scale=2, min_width=120):
            generate_btn = gr.Button(
                value=C.GENERATE_BUTTON_LABEL,
                variant="primary",
                interactive=True,
                elem_id="generate-btn",
            )

    # Listening
    with gr.Group(visible=False) as row_listening:
        # Audio players (hidden until after generate)
        with gr.Row():
            with gr.Column():
                a_music_player = gr.Audio(
                    value=STATIC_DIR / "debug-a.mp3" if debug else None,
                    label=C.AUDIO_PLAYER_A_LABEL,
                    visible=True,
                    interactive=False,
                    show_download_button=False,
                    show_share_button=False,
                    elem_id="a-music-player",
                )
            with gr.Column():
                b_music_player = gr.Audio(
                    value=STATIC_DIR / "debug-b.mp3" if debug else None,
                    label=C.AUDIO_PLAYER_B_LABEL,
                    visible=True,
                    interactive=False,
                    show_download_button=False,
                    show_share_button=False,
                    elem_id="b-music-player",
                )

        # Battle UUID (hidden until after generate)
        with gr.Row():
            battle_uuid = gr.Markdown("", visible=False, elem_id="battle-uuid")

        # Lyrics overview
        with gr.Row(visible=False):
            with gr.Column():
                a_lyrics = gr.Markdown("", visible=False, elem_id="a-lyrics")
            with gr.Column():
                b_lyrics = gr.Markdown("", visible=False, elem_id="b-lyrics")

        # System identity labels (hidden until after vote)
        with gr.Row():
            a_system_tag = gr.Markdown(
                C.HIDDEN_TAG_LABEL, visible=False, elem_id="a-system-tag"
            )
            b_system_tag = gr.Markdown(
                C.HIDDEN_TAG_LABEL, visible=False, elem_id="b-system-tag"
            )

    # Voting status
    with gr.Row(visible=False) as row_vote_status:
        # Vote status text (hidden until after generate)
        vote_status_markdown = gr.Markdown(
            C.VOTE_ALLOWED_MSG if debug else C.VOTE_NOT_ALLOWED_MSG,
            visible=debug,
            elem_id="vote-status-text",
        )

    # Vote
    with gr.Row(visible=False) as row_vote_buttons:
        # Vote buttons (hidden until generating, interactable after listening)
        vote_a_btn = gr.Button(
            value=C.BUTTON_A_BETTER,
            interactive=True,
            visible=debug,
            scale=1,
            variant="primary",
            elem_id="vote-a-btn",
        )
        vote_b_btn = gr.Button(
            value=C.BUTTON_B_BETTER,
            interactive=True,
            visible=debug,
            scale=1,
            variant="primary",
            elem_id="vote-b-btn",
        )
    with gr.Row(visible=False) as row_vote_buttons_2:
        with gr.Column(scale=1):
            pass
        with gr.Column(scale=2):
            with gr.Row():
                vote_tie_btn = gr.Button(
                    value=C.BUTTON_TIE,
                    interactive=True,
                    visible=debug,
                    scale=1,
                    variant="secondary",
                    elem_id="vote-tie-btn",
                )
                vote_both_bad_btn = gr.Button(
                    value=C.BUTTON_BOTH_BAD,
                    interactive=True,
                    visible=debug,
                    scale=1,
                    variant="secondary",
                    elem_id="vote-both-bad-btn",
                )
        with gr.Column(scale=1):
            pass

    # Action buttons (hidden until after generate)
    with gr.Row(visible=False) as row_action_buttons:
        # Download button (hidden until after vote)
        download_file = gr.File(
            label=C.DOWNLOAD_FILE_LABEL, visible=False, elem_id="download-file"
        )
        new_round_btn = gr.Button(
            value=C.NEW_ROUND_BUTTON,
            visible=debug,
            elem_id="new-round-btn",
        )
        regenerate_btn = gr.Button(
            value=C.REGENERATE_BUTTON,
            visible=debug,
            elem_id="regenerate-btn",
        )

    return {
        # Core visibility rows
        "rows": [
            row_input,
            row_listening,
            row_vote_status,
            row_vote_buttons,
            row_vote_buttons_2,
            row_action_buttons,
            row_info,
        ],
        # Input
        "prompt_textbox": prompt_textbox,
        "prompt_textbox_col": prompt_textbox_col,
        "prebake_btn": prebake_btn,
        "prebake_btn_col": prebake_btn_col,
        "generate_btn": generate_btn,
        # Listening section
        "battle_uuid": battle_uuid,
        "a_music_player": a_music_player,
        "b_music_player": b_music_player,
        "a_lyrics": a_lyrics,
        "b_lyrics": b_lyrics,
        "a_system_tag": a_system_tag,
        "b_system_tag": b_system_tag,
        # Voting section
        "vote_status_markdown": vote_status_markdown,
        "vote_a_btn": vote_a_btn,
        "vote_b_btn": vote_b_btn,
        "vote_tie_btn": vote_tie_btn,
        "vote_both_bad_btn": vote_both_bad_btn,
        # Final action section
        "download_file": download_file,
        "new_round_btn": new_round_btn,
        "regenerate_btn": regenerate_btn,
        # Info section
        "model_description_markdown": model_description_markdown,
    }


def build_ui(debug=False):
    """Build the complete demo interface"""
    _LOGGER.info("Building demo UI")
    ui = {}
    gr.Markdown(C.TITLE_MD, elem_id="title")
    with gr.Tabs():
        with gr.TabItem(C.TAB_ARENA, elem_id="tab-arena"):
            # Build TOS UI
            _LOGGER.info("Building TOS UI")
            ui["tos"] = build_ui_tos(debug=debug)

            # Build no ack UI
            with gr.Row(elem_id="no-ack-row", visible=False) as row_no_ack:
                gr.Markdown(C.NEEDS_ACK_TOS_MD)
            ui["no_ack"] = {"rows": [row_no_ack]}

            # Build battle UI
            _LOGGER.info("Building battle UI")
            ui["battle"] = build_ui_battle(debug=debug)

            # Build no gateway UI
            with gr.Row(elem_id="no-gateway-row", visible=False) as row_no_gateway:
                gr.Markdown(C.GATEWAY_UNAVAILABLE_MD)
            ui["no_gateway"] = {"rows": [row_no_gateway]}

        with gr.TabItem(C.TAB_DIRECT, elem_id="tab-direct"):
            gr.Markdown(C.DIRECT_MD)

        with gr.TabItem(C.TAB_LEADERBOARD, elem_id="tab-leaderboard"):
            gr.Markdown(C.LEADERBOARD_COMING_SOON_MD)

        with gr.TabItem(C.TAB_ABOUT, elem_id="tab-about"):
            gr.Markdown(C.ABOUT_MD, elem_id="about-markdown")

    ui["new_battle"] = [
        ui["battle"][a]
        for a in [
            "battle_uuid",
            "a_music_player",
            "b_music_player",
            "a_lyrics",
            "b_lyrics",
            "a_system_tag",
            "b_system_tag",
            "vote_status_markdown",
            "vote_a_btn",
            "vote_b_btn",
            "vote_tie_btn",
            "vote_both_bad_btn",
            "download_file",
            "new_round_btn",
            "regenerate_btn",
        ]
    ]

    return ui


def build_demo(debug=False):
    """Build the complete demo interface"""
    # Build UI
    _LOGGER.info("Building demo")
    with gr.Blocks(
        title=C.GR_TITLE,
        css=load_static_file("style.css"),
        analytics_enabled=False,
    ) as demo:
        # Init UI
        _LOGGER.info("Initializing UI")
        ui = build_ui(debug=debug)

        # Init state (placeholders for info specific to each session)
        _LOGGER.info("Initializing state")
        state = {
            "session": gr.State(None),
            "user": gr.State(None),
            "battle": gr.State(None),
            "vote": gr.State(None),
            "systems": gr.State(None),
            "prebaked": gr.State(None),
            "detailed_prompt": gr.State(None),
            "frontend": {
                "voting_enabled": gr.State(False),
            },
        }

        # Bind event handlers that run on load
        _LOGGER.info("Binding onload event handlers")
        bind_onload_events(demo=demo, ui=ui, state=state, debug=debug)

        # Bind event handlers that run on UI events
        _LOGGER.info("Binding UI event handlers")
        bind_ui_events(ui=ui, state=state, debug=debug)

    return demo


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument(
        "--share", action="store_true", help="Generate a public, shareable link"
    )
    parser.add_argument("--queue", action="store_true", help="Enable Gradio queue")
    parser.add_argument(
        "--concurrency-count",
        type=int,
        default=1,
        help="Gradio queue concurrency count",
    )
    parser.add_argument(
        "--max-threads",
        type=int,
        default=1,
        help="Maximum number of threads to use for the demo",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug UI mode (shows more UI elements than normal)",
    )

    logging.basicConfig(level=logging.INFO)

    args = parser.parse_args()
    _LOGGER.info(f"Starting with args: {args}")

    demo = build_demo(debug=args.debug)
    _LOGGER.info("Demo built")

    if args.queue:
        _LOGGER.info("Enabling Gradio queue")
        demo.queue(
            default_concurrency_limit=args.concurrency_count,
            status_update_rate="auto",
            api_open=False,
        )

    app, local_url, share_url = demo.launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        max_threads=args.max_threads,
        debug=args.debug,
        prevent_thread_lock=True,
    )

    _LOGGER.info(f"Local URL: {local_url}")
    _LOGGER.info(f"Share URL: {share_url}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        _LOGGER.info("Shutting down...")

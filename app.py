
import streamlit as st

from pipeline import (
    blog_to_script,
    generate_audio,
    validate_script,
    ScriptValidationError,
    MAX_SCRIPT_CHARS,
)

st.set_page_config(
    page_title="Blog to Podcast",
    page_icon="🎙️",
    layout="wide"
)

st.title("Blog to Podcast 🎙️")
st.write(
    "Transform your favorite blog posts into "
    "engaging podcast episodes!"
)

# Initialize session state
if "script" not in st.session_state:
    st.session_state.script = ""

if "audio" not in st.session_state:
    st.session_state.audio = None

if "script_url" not in st.session_state:
    st.session_state.script_url = None


def update_script():
    # Audio no longer matches if the script changes
    st.session_state.audio = None


# Blog URL input
url = st.text_input(
    "Enter a blog URL",
    placeholder="https://example.com/blog"
)

# STEP 1: Generate script
if st.button("Generate Script", type="primary"):
    st.session_state.script = ""
    st.session_state.audio = None
    st.session_state.script_url = None

    if not url.strip():
        st.warning("Please enter a blog URL.")
    else:
        try:
            with st.spinner("Reading blog and generating script..."):
                script = blog_to_script(url)

            st.session_state.script = script
            st.session_state.script_url = url
            st.success("Script generated successfully!")

        except ScriptValidationError as e:
            st.session_state.script = e.script
            st.session_state.script_url = url
            st.warning(f"Script needs editing: {e}")

        except Exception as e:
            st.error(str(e))


# STEP 2: Review/edit script
if st.session_state.script:
    if st.session_state.script_url != url:
        st.warning(
            "The URL has changed. Generate a new script "
            "to use the current article."
        )
    else:
        st.subheader("Generated Podcast Script")

        # Keep editor value synchronized after generation
        if (
            "script_editor" not in st.session_state
            or st.session_state.get("editor_source")
            != st.session_state.script
        ):
            st.session_state.script_editor = (
                st.session_state.script
            )
            st.session_state.editor_source = (
                st.session_state.script
            )

        edited_script = st.text_area(
            "Review or edit your script",
            key="script_editor",
            height=300,
            on_change=update_script
        )

        st.caption(
            f"{len(edited_script)} / "
            f"{MAX_SCRIPT_CHARS} characters"
        )

        # STEP 3: Generate audio
        if st.button("Generate Audio"):
            is_valid, reason, validated_script = (
                validate_script(
                    edited_script,
                    max_chars=MAX_SCRIPT_CHARS,
                    status="completed"
                )
            )

            if not is_valid:
                st.error(reason)
            else:
                try:
                    with st.spinner("Generating audio..."):
                        st.session_state.audio = (
                            generate_audio(validated_script)
                        )

                    st.success("Podcast generated!")

                except Exception as e:
                    st.error(str(e))


# STEP 4: Play and download audio
if st.session_state.audio:
    st.subheader("🎧 Listen to Your Podcast")

    st.audio(
        st.session_state.audio,
        format="audio/mpeg"
    )

    st.download_button(
        "⬇️ Download Podcast",
        data=st.session_state.audio,
        file_name="podcast.mp3",
        mime="audio/mpeg"
    )

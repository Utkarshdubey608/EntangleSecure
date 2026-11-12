"""Page 7 — One-time-pad messaging with the E91 key."""

from __future__ import annotations

import streamlit as st

from entanglesecure.protocol.messaging import decrypt, encrypt, required_key_bits

from .. import components, state


def render() -> None:
    res = state.result()
    k = res.keys
    key = k.final_alice
    available = int(key.size)

    components.page_header(
        "Quantum-secured messaging",
        "Encrypt a message with the secret key that E91 just distilled. Each message bit is XORed with one key bit, "
        "so the key can be used only once and must be at least as long as the message.",
    )
    components.stat_strip([
        ("Secret key available", f"{available:,}<small>bits</small>", "from the current E91 run"),
        ("Key status", components.status_badge(res.security_status), "Bell test and key checks"),
    ])

    if available == 0:
        components.note("No secret key is available for this run, so there is nothing to encrypt with. "
                        "Change the configuration in the laboratory and try again.")
        return

    text = st.text_area("Message", value="Meet at the lab at 9:00.", height=120, max_chars=2000)
    needed = required_key_bits(text)
    if needed > available:
        st.error(f"Key too short: this message needs {needed:,} bits, but only {available:,} are available. "
                 "Shorten the message or increase the number of pairs.")
        return

    cipher = encrypt(text, key)
    recovered = decrypt(cipher, key)
    st.caption(f"Uses {needed:,} of {available:,} key bits. The key is consumed and must not be reused.")
    c1, c2 = st.columns(2)
    with c1:
        components.panel("Ciphertext (hex)", f'<div class="es-bits">{cipher.hex() or "—"}</div>')
    with c2:
        bits = "".join(f"{b:08b}" for b in cipher)
        components.panel("Ciphertext (binary)", f'<div class="es-bits">{bits or "—"}</div>')
    if recovered == text:
        components.note("Round trip OK: decrypting with the same key recovers the original message.")
    else:
        st.error("Round trip failed: the decrypted text differs from the original.")

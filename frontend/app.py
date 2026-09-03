"""Authentication-only Streamlit shell; business workflows remain separate."""

from __future__ import annotations

import os

import streamlit as st
from streamlit_cookies_manager import EncryptedCookieManager

from services.api_client import AuthApiClient, AuthenticationApiError

COOKIE_PREFIX = "cim_auth_"
ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"


def _cookies() -> EncryptedCookieManager:
    secret = os.getenv("STREAMLIT_COOKIE_SECRET")
    if not secret:
        st.error("Authentication is unavailable: STREAMLIT_COOKIE_SECRET is not configured.")
        st.stop()
    cookies = EncryptedCookieManager(prefix=COOKIE_PREFIX, password=secret)
    if not cookies.ready():
        st.stop()
    return cookies


def _clear_auth(cookies: EncryptedCookieManager) -> None:
    for key in (ACCESS_COOKIE, REFRESH_COOKIE):
        cookies[key] = ""
    cookies.save()
    for key in ("access_token", "refresh_token", "auth_user"):
        st.session_state.pop(key, None)


def _save_tokens(cookies: EncryptedCookieManager, tokens: dict) -> None:
    """Persist encrypted values; never place tokens in URLs or logs."""
    cookies[ACCESS_COOKIE] = tokens["access_token"]
    cookies[REFRESH_COOKIE] = tokens["refresh_token"]
    cookies.save()
    st.session_state.access_token = tokens["access_token"]
    st.session_state.refresh_token = tokens["refresh_token"]


def _restore_session(client: AuthApiClient, cookies: EncryptedCookieManager) -> bool:
    access_token = st.session_state.get("access_token") or cookies.get(ACCESS_COOKIE)
    refresh_token = st.session_state.get("refresh_token") or cookies.get(REFRESH_COOKIE)
    if not access_token and not refresh_token:
        return False
    if access_token:
        try:
            st.session_state.auth_user = client.me(access_token)
            st.session_state.access_token = access_token
            st.session_state.refresh_token = refresh_token
            return True
        except AuthenticationApiError:
            pass
    if refresh_token:
        try:
            tokens = client.refresh(refresh_token)
            _save_tokens(cookies, tokens)
            st.session_state.auth_user = client.me(tokens["access_token"])
            return True
        except AuthenticationApiError:
            pass
    _clear_auth(cookies)
    return False


def _login_or_register(client: AuthApiClient, cookies: EncryptedCookieManager) -> None:
    login_tab, register_tab = st.tabs(["Login", "Register"])
    with login_tab:
        with st.form("login"):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Login")
        if submitted:
            try:
                tokens = client.login(username=username, password=password)
                _save_tokens(cookies, tokens)
                st.session_state.auth_user = client.me(tokens["access_token"])
                st.rerun()
            except AuthenticationApiError as exc:
                st.error(str(exc))
    with register_tab:
        with st.form("register"):
            username = st.text_input("Username", key="register_username")
            email = st.text_input("Email", key="register_email")
            password = st.text_input("Password", type="password", key="register_password")
            submitted = st.form_submit_button("Register")
        if submitted:
            try:
                client.register(username=username, email=email, password=password)
                st.success("Registration successful. You can now log in.")
            except AuthenticationApiError as exc:
                st.error(str(exc))


def main() -> None:
    st.set_page_config(page_title="CIM", page_icon="🔐")
    client, cookies = AuthApiClient(), _cookies()
    if not _restore_session(client, cookies):
        st.title("Sign in")
        _login_or_register(client, cookies)
        return
    user = st.session_state.auth_user
    st.sidebar.write(f"Signed in as **{user['username']}**")
    if st.sidebar.button("Logout"):
        try:
            client.logout(st.session_state.refresh_token)
        except AuthenticationApiError:
            pass  # Clear local state even if the server session already expired.
        _clear_auth(cookies)
        st.rerun()
    st.title("Authenticated session")
    st.write("Authentication is active. Application pages may now use the authenticated identity.")


if __name__ == "__main__":
    main()

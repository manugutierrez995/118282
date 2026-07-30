import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolveRoute, safeNext } from "../src/router/router.js";

test("account and authentication routes resolve centrally", () => {
  assert.deepEqual(resolveRoute({pathname:"/account",search:""}), {kind:"redirect",to:"/account/profile"});
  for (const path of ["/login","/signup","/forgot-password","/reset-password","/account/profile","/account/bookmarks","/account/settings"])
    assert.equal(resolveRoute({pathname:path,search:""}).pathname, path);
  assert.equal(resolveRoute({pathname:"/account/nope",search:""}).kind, "account-not-found");
});
test("legacy reader query remains supported", () => {
  assert.equal(resolveRoute({pathname:"/reader",search:"?work=A&chapter=chapter_1"}).kind, "legacy-reader");
  assert.equal(resolveRoute({pathname:"/",search:"?work=A&chapter=chapter_1"}).kind, "legacy-reader");
});
test("return paths accept only known private relative routes", () => {
  assert.equal(safeNext("/account/bookmarks?sort=new#saved"), "/account/bookmarks?sort=new#saved");
  for (const unsafe of ["https://evil.test/account/profile","//evil.test/x","javascript:alert(1)","/login","/%2f%2fevil.test"])
    assert.equal(safeNext(unsafe), "/account/profile");
});
test("one client and one auth subscription are application-owned", async () => {
  const client = await readFile(new URL("../src/auth/supabase.js", import.meta.url), "utf8");
  const session = await readFile(new URL("../src/auth/session.js", import.meta.url), "utf8");
  const discussion = await readFile(new URL("../src/discussion/supabase.js", import.meta.url), "utf8");
  assert.equal((client.match(/createClient\(/g)||[]).length, 1);
  assert.equal((session.match(/onAuthStateChange\(/g)||[]).length, 1);
  assert.doesNotMatch(discussion, /createClient\(/);
});
test("preference migration enforces owner RLS for every operation", async () => {
  const sql = await readFile(new URL("../supabase/migrations/202607300001_user_tag_preferences.sql", import.meta.url), "utf8");
  for (const operation of ["select","insert","update","delete"]) assert.match(sql, new RegExp(`own_${operation}`));
  assert.match(sql, /primary key \(user_id, tag_key\)/);
  assert.match(sql, /auth\.uid\(\)/);
});

import { normalizeAuthError } from "../src/auth/errors.js";
import { safeOAuthReturnPath, oauthRedirectUrl } from "../src/auth/session.js";
import { accountMenuMarkup, accountPresentation } from "../src/account/navigation.js";

test("OAuth return paths and redirect URLs stay on an allowlisted account route", () => {
  assert.equal(safeOAuthReturnPath("/account/settings?from=login"), "/account/settings?from=login");
  for (const value of ["https://evil.test/account/profile", "//evil.test", "/login", "/account/profile\\evil"])
    assert.equal(safeOAuthReturnPath(value), "/account/profile");
  assert.equal(oauthRedirectUrl("/account/bookmarks", "https://doku.example"), "https://doku.example/account/bookmarks");
});

test("Google failures retain safe, useful categories", () => {
  assert.equal(normalizeAuthError(new Error("Unsupported provider: google")).code, "provider_disabled");
  assert.equal(normalizeAuthError(new Error("redirect_uri_mismatch")).code, "callback_mismatch");
  assert.equal(normalizeAuthError(new TypeError("Failed to fetch")).code, "network");
  assert.doesNotMatch(normalizeAuthError(new Error("mystery")).userMessage, /undefined/);
});

test("profile metadata fallback and disclosure are provider-neutral", () => {
  assert.deepEqual(accountPresentation({id:"uuid-a", user_metadata:{}, email:null}), {name:"Doku-Doujin member",email:"Email unavailable",avatar:"",fallback:"D"});
  const google = accountPresentation({id:"uuid-g",email:"g@example.test",user_metadata:{name:"G User",picture:"https://images.example/avatar.png"}});
  assert.equal(google.avatar, "https://images.example/avatar.png");
  const menu = accountMenuMarkup({email:"g@example.test",user_metadata:{name:"G User"}}, "menu-test");
  for (const label of ["Profile", "Bookmarks", "Settings", "Sign out"]) assert.match(menu, new RegExp(label));
  assert.match(menu, /aria-expanded="false"/); assert.match(menu, /aria-controls="menu-test"/);
});

test("Google account isolation operations remain explicit", async () => {
  const session = await readFile(new URL("../src/auth/session.js", import.meta.url), "utf8");
  assert.match(session, /signInWithOAuth\(options\)/);
  assert.match(session, /state\.user\?\.is_anonymous/);
  assert.match(session, /VITE_ENABLE_ANONYMOUS_GOOGLE_LINKING/);
  assert.match(session, /if \(state\.user\) await signOut\(\)/);
  assert.match(session, /identityGeneration\+\+/);
  assert.match(session, /openid email profile/);
  assert.doesNotMatch(session, /drive|gmail|contacts/i);
});

test("bookmark rendering and query are tied to current UUID and reject stale results", async () => {
  const data = await readFile(new URL("../src/account/data.js", import.meta.url), "utf8");
  const views = await readFile(new URL("../src/account/views.js", import.meta.url), "utf8");
  assert.match(data, /from\("bookmarks"\).*eq\("user_id", userId\)/s);
  assert.match(views, /isCurrentIdentity\(user\.id, identityGeneration\)/);
  assert.doesNotMatch(data, /google_bookmarks|email_bookmarks|provider.*bookmark/i);
});

test("tag handoff contains implementation architecture", async () => {
  const handoff = await readFile(new URL("../tags-latest.md", import.meta.url), "utf8");
  for (const heading of ["Required vocabulary and schema", "Exclusion pipeline", "Preferred weighting", "Settings UI", "Security, privacy", "Tests and rollout order", "Exact next Codex task"])
    assert.match(handoff, new RegExp(heading, "i"));
  assert.match(handoff, /Rotunda\.start/); assert.match(handoff, /exclusion always wins/i);
});

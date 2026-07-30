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

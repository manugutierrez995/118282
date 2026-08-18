import test from "node:test";
import assert from "node:assert/strict";
import { resolveRoute } from "../src/router/router.js";

test("a 7-digit public work ID resolves as a work-id route", () => {
    assert.deepEqual(
        resolveRoute({ pathname: "/1199999", search: "" }),
        {
            kind: "work-id",
            id: "1199999",
            pathname: "/1199999"
        }
    );
});

test("a root-level work slug resolves as a work-slug route", () => {
    assert.deepEqual(
        resolveRoute({ pathname: "/Chu_Berozu_decensored", search: "" }),
        {
            kind: "work-slug",
            work: "Chu_Berozu_decensored",
            pathname: "/Chu_Berozu_decensored"
        }
    );
});

test("encoded root-level work slugs decode before lookup", () => {
    assert.equal(
        resolveRoute({ pathname: "/Some%20Work", search: "" }).work,
        "Some Work"
    );
});

test("existing application routes keep priority over work IDs and slugs", () => {
    assert.equal(resolveRoute({ pathname: "/", search: "" }).kind, "home");
    assert.equal(resolveRoute({ pathname: "/profiles", search: "" }).kind, "profiles");
    assert.equal(resolveRoute({ pathname: "/account/profile", search: "" }).kind, "account-profile");
});

test("legacy query reader URLs keep priority", () => {
    assert.equal(
        resolveRoute({ pathname: "/1199999", search: "?work=foo&chapter=chapter_1" }).kind,
        "legacy-reader"
    );
});

test("nested unknown paths and malformed encoding remain not-found", () => {
    assert.equal(resolveRoute({ pathname: "/foo/bar", search: "" }).kind, "not-found");
    assert.equal(resolveRoute({ pathname: "/%E0%A4%A", search: "" }).kind, "not-found");
});

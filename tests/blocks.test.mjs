import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = (await readFile(new URL("../src/components/blocks.js", import.meta.url), "utf8"))
    .replace('import blocksData from "../data/blocks.json";', "const blocksData = {};");
const { renderBlocksIntoContainers, resolveBlockBackground } = await import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
);

class Node {
    constructor(tagName = "fragment") {
        this.tagName = tagName;
        this.children = [];
        this.style = {};
        this.attributes = [];
        this.classList = { add: name => { this.className += ` ${name}`; } };
    }
    appendChild(child) { this.children.push(child); return child; }
    replaceChildren(...children) {
        this.children = children.flatMap(child => child.tagName === "fragment" ? child.children : [child]);
    }
    setAttribute(name, value) { this[name] = String(value); }
}

class Template extends Node {
    constructor() {
        super("template");
        this.content = new Node();
        this.content.querySelectorAll = () => this.scripts;
    }
    set innerHTML(value) {
        this.scripts = /<script/i.test(value) ? [new Script()] : [];
        this.content.cloneNode = () => {
            const clone = new Node();
            clone.children = this.scripts.map(script => script.replacement || script);
            return clone;
        };
    }
}

class Script extends Node {
    constructor() {
        super("script");
        this.textContent = "window.blockRan = true";
        this.attributes = [{ name: "data-test", value: "preserved" }];
    }
    replaceWith(replacement) { this.replacement = replacement; }
}

globalThis.document = {
    createDocumentFragment: () => new Node(),
    createElement: tag => tag === "template" ? new Template() : tag === "script" ? new Script() : new Node(tag),
    querySelector: () => null
};
globalThis.fetch = async () => ({ ok: true, text: async () => "<div>html</div><script data-test=\"preserved\">window.blockRan = true</script>" });

test("background priority and hard black fallback work without global CSS", () => {
    assert.equal(resolveBlockBackground({}, { background: "#123456" }), "#123456");
    assert.equal(resolveBlockBackground({ background: "#abcdef" }, { background: "#123456" }), "#abcdef");
    assert.equal(resolveBlockBackground({ background: "not a color!" }, { background: "#123456" }), "#123456");
    assert.equal(resolveBlockBackground({ background: "unsupported" }, { background: "#123456" }), "#123456");
    assert.equal(resolveBlockBackground({}, { background: "" }), "#000000");
    assert.equal(resolveBlockBackground({}, undefined), "#000000");
});

test("all existing block types render in order and defaults is not a placement", async () => {
    const left = new Node("target");
    const config = {
        defaults: { background: "#101010" },
        left: [
            { html: "/example.html" },
            { image: "/example.png", background: "#abcdef" },
            { iframe: "https://example.com", background: "unsupported" },
            { type: "rail-ad", src: "https://example.com/ad" },
            { text: "copy" },
            { embed: "<strong>embed</strong>" }
        ],
        center: [],
        right: []
    };

    await renderBlocksIntoContainers({ blocksData: config, left, center: null, right: null });

    assert.deepEqual(left.children.map(child => child.className), [
        "site-block html-block",
        "site-block image-block",
        "site-block iframe-block",
        "site-block rail-ad-block",
        "site-block text-block",
        "site-block embed-block"
    ]);
    assert.deepEqual(left.children.map(child => child.style.backgroundColor), [
        "#101010", "#abcdef", "#101010", "#101010", "#101010", "#101010"
    ]);
    assert.equal(left.children.length, config.left.length);
});

test("HTML scripts are recreated with their attributes and text", async () => {
    const left = new Node("target");
    await renderBlocksIntoContainers({
        blocksData: { defaults: { background: "#000" }, left: [{ html: "/example.html" }] },
        left,
        center: null,
        right: null
    });

    const recreated = left.children[0].children[0].children[0];
    assert.equal(recreated.tagName, "script");
    assert.equal(recreated["data-test"], "preserved");
    assert.equal(recreated.textContent, "window.blockRan = true");
});

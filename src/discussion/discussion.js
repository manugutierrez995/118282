import "../styles/discussion.css";
import { isDiscussionConfigured } from "./supabase.js";
import { appendPlainTextWithLinks } from "./text.js";

const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
};
const draftKey = workId => `doku-doujin:discussion-draft:${workId}`;

export function mountDiscussion(parent, workId) {
    const section = el("section", "discussion-shell");
    section.setAttribute("aria-labelledby", `discussion-heading-${workId}`);
    section.dataset.workId = String(workId);
    const head = el("div", "discussion-heading");
    const heading = el("h2", "", "OPEN DISCUSSION");
    heading.id = `discussion-heading-${workId}`;
    head.append(heading, el("p", "", "Accounts welcome. Anonymity permitted."));
    const controls = el("div", "discussion-head-controls");
    const bookmark = el("button", "discussion-button", "Bookmark");
    bookmark.type = "button"; bookmark.setAttribute("aria-pressed", "false");
    controls.append(bookmark); head.append(controls); section.append(head);
    const status = el("p", "discussion-status", "Discussion will load as you approach.");
    status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite");
    section.append(status); parent.append(section);

    let disposed = false, loaded = false, cursor = null, service, comments = [], userSession = null;
    let observer;
    const cleanups = [];
    const listen = (node, event, fn) => { node.addEventListener(event, fn); cleanups.push(() => node.removeEventListener(event, fn)); };
    const setStatus = (message, error = false) => { status.textContent = message; status.classList.toggle("is-error", error); };

    async function init() {
        if (loaded || disposed) return;
        loaded = true;
        if (!isDiscussionConfigured()) { setStatus("Discussion is currently unavailable."); bookmark.disabled = true; return; }
        setStatus(navigator.onLine ? "Loading discussion…" : "You appear to be offline. Retry when connected.", !navigator.onLine);
        try {
            service = await import("./service.js");
            const auth = await import("./supabase.js");
            userSession = await auth.session();
            renderAccount(auth);
            await Promise.all([refresh(), updateBookmark()]);
        } catch (error) { if (!disposed) setStatus(error.message || "Unable to load discussion. Retry.", true); }
    }

    function renderAccount(auth) {
        const bar = el("div", "discussion-account");
        const label = el("span", "", userSession ? (userSession.user.is_anonymous ? "Anonymous session" : "Signed in") : "Not signed in");
        const google = el("button", "discussion-button", userSession?.user?.is_anonymous ? "Link Google account" : "Continue with Google"); google.type = "button";
        listen(google, "click", async () => { sessionStorage.setItem(draftKey(workId), section.querySelector("textarea")?.value || ""); try { await auth.continueWithGoogle(); } catch (e) { setStatus(e.message, true); } });
        bar.append(label, google);
        if (userSession) { const signout = el("button", "discussion-button", "Sign out"); signout.type = "button"; listen(signout, "click", async () => { const sessionService = await import("../auth/session.js"); await sessionService.signOut(); userSession = null; section.querySelector(".discussion-account")?.remove(); renderAccount(auth); }); bar.append(signout); }
        head.after(bar);
    }

    async function updateBookmark() {
        const active = await service.bookmarkState(workId);
        bookmark.setAttribute("aria-pressed", String(active)); bookmark.textContent = active ? "Bookmarked" : "Bookmark";
    }
    listen(bookmark, "click", async () => { bookmark.disabled = true; try { const active = bookmark.getAttribute("aria-pressed") === "true"; const next = await service.toggleBookmark(workId, active); bookmark.setAttribute("aria-pressed", String(next)); bookmark.textContent = next ? "Bookmarked" : "Bookmark"; } catch (e) { setStatus(e.message, true); } finally { bookmark.disabled = false; } });

    async function refresh(older = false) {
        const generationWork = section.dataset.workId;
        const result = await service.loadDiscussion(workId, older ? cursor : null);
        if (disposed || generationWork !== String(workId)) return;
        comments = older ? [...comments, ...result.comments] : result.comments;
        cursor = result.nextCursor;
        renderList(); setStatus(comments.length ? (cursor ? "Discussion loaded." : "End of discussion.") : "No comments yet. Start the discussion.");
    }

    function renderList() {
        section.querySelector(".discussion-body")?.remove();
        const body = el("div", "discussion-body"); body.append(makeComposer());
        const list = el("ol", "discussion-list");
        for (const comment of comments) list.append(renderComment(comment));
        body.append(list);
        const more = el("button", "discussion-button discussion-more", cursor ? "Load older comments" : "End of discussion"); more.type = "button"; more.disabled = !cursor;
        listen(more, "click", () => refresh(true).catch(e => setStatus(e.message, true)));
        const retry = el("button", "discussion-button", "Refresh"); retry.type = "button"; listen(retry, "click", () => refresh().catch(e => setStatus(e.message, true)));
        body.append(more, retry); section.append(body);
    }

    function makeComposer(parentId = null, existing = null) {
        const form = el("form", "discussion-composer");
        const label = el("label", "", existing ? "Edit comment" : parentId ? "Write a reply" : "Join the discussion");
        const textarea = el("textarea"); textarea.maxLength = 2000; textarea.rows = 4; textarea.required = true; textarea.value = existing?.body || (!parentId ? sessionStorage.getItem(draftKey(workId)) || "" : "");
        label.append(textarea); const counter = el("span", "discussion-counter", `${textarea.value.length} / 2000`);
        const mode = el("select"); mode.setAttribute("aria-label", "Posting identity");
        const account = el("option", "", "Post as my account"); account.value = "account"; const anonymous = el("option", "", "Post anonymously"); anonymous.value = "anonymous";
        if (!userSession || userSession.user.is_anonymous) mode.append(anonymous); else mode.append(account, anonymous);
        const submit = el("button", "discussion-button discussion-primary", existing ? "Save" : "Post"); submit.type = "submit";
        listen(textarea, "input", () => { counter.textContent = `${textarea.value.length} / 2000`; if (!parentId) sessionStorage.setItem(draftKey(workId), textarea.value); });
        listen(textarea, "keydown", event => { if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) form.requestSubmit(); });
        listen(form, "submit", async event => { event.preventDefault(); const value = textarea.value.trim(); if (!value) { setStatus("Comment cannot be empty.", true); return; } submit.disabled = true; try { if (existing) await service.editComment(existing.id, value); else await service.createComment(workId, value, mode.value, parentId); sessionStorage.removeItem(draftKey(workId)); await refresh(); setStatus(existing ? "Comment updated." : "Comment posted."); } catch (e) { setStatus(e.message, true); } finally { submit.disabled = false; } });
        form.append(label, counter, mode, submit); return form;
    }

    function renderComment(comment) {
        const item = el("li", `discussion-comment${comment.parent_id ? " is-reply" : ""}`); item.dataset.commentId = comment.id;
        const article = el("article"); const meta = el("header", "discussion-comment-meta");
        meta.append(el("strong", "", comment.display_mode === "account" ? (comment.display_name || "Account") : "Anonymous"));
        const time = el("time", "", new Date(comment.created_at).toLocaleString()); time.dateTime = comment.created_at; meta.append(time);
        const content = el("p", "discussion-comment-text");
        if (comment.deleted_at) content.textContent = "[Comment removed]"; else appendPlainTextWithLinks(content, comment.body);
        if (comment.edited_at && !comment.deleted_at) content.append(el("span", "discussion-edited", " (edited)"));
        article.append(meta, content);
        if (!comment.deleted_at) {
            const actions = el("div", "discussion-actions");
            const action = (text, fn) => { const b = el("button", "discussion-action", text); b.type = "button"; listen(b, "click", fn); actions.append(b); };
            action(`Vote ${comment.score ?? 0}`, () => service.voteComment(comment.id).then(refresh).catch(e => setStatus(e.message, true)));
            if (!comment.parent_id) action("Reply", () => { const composer = makeComposer(comment.id); item.append(composer); composer.querySelector("textarea").focus(); });
            action("Report", () => { const reason = window.prompt("Report reason: spam, harassment, or other"); if (reason) service.reportComment(comment.id, reason).then(() => setStatus("Report received.")).catch(e => setStatus(e.message, true)); });
            if (comment.is_author) { action("Edit", () => { const composer = makeComposer(null, comment); item.append(composer); composer.querySelector("textarea").focus(); }); action("Delete", () => service.deleteComment(comment.id).then(refresh).catch(e => setStatus(e.message, true))); }
            article.append(actions);
        }
        item.append(article);
        for (const reply of comment.replies || []) item.append(renderComment(reply));
        return item;
    }

    if ("IntersectionObserver" in window) { observer = new IntersectionObserver(entries => { if (entries.some(e => e.isIntersecting)) { observer.disconnect(); init(); } }, { rootMargin: "700px 0px" }); observer.observe(section); }
    else init();
    return () => { disposed = true; observer?.disconnect(); cleanups.splice(0).forEach(fn => fn()); section.remove(); };
}

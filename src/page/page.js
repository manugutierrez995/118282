import { Landing } from "./landing.js";
import { Reader } from "./reader.js";
import { loadWork, workSource } from "../storage/work_manifest.js";
import { getLocalProfileState, subscribeLocalProfiles } from "../local-profile/store.js";
import { startRouter, navigate, workUrl } from "../router/router.js";
import { bookmarksView, notFoundView, profileView, profilesView, settingsView } from "../account/views.js";
let currentRoute,generation=0; const root=()=>document.getElementById('reader-container'),focus=()=>requestAnimationFrame(()=>root()?.querySelector('h1')?.focus());
function showNotFound(account=false){notFoundView(root(),account);return focus()}
async function openWorkRoute(route,{canonicalize=false, id=generation}={}){
    const work=await loadWork(route.work);
    if(id!==generation) return;
    if(!work) return showNotFound();
    const chapters=work.chapters||[];
    if(!chapters.length) return showNotFound();
    const chapter=route.chapter&&chapters.includes(route.chapter)?route.chapter:chapters[0];
    const canonical=workUrl(work.slug, chapter===chapters[0]?null:chapter);
    if(canonicalize) return navigate(canonical,{replace:true});
    return Reader.start(work.slug,chapter,{source:workSource(work)});
}
async function render(route){const id=++generation;document.body.classList.remove('reader-active');if(route.kind==='redirect')return navigate(route.to,{replace:true});if(route.kind==='legacy-reader')return openWorkRoute(route,{canonicalize:true,id});if(route.kind==='work'){await openWorkRoute(route,{id});return;}if(route.kind==='home')return Landing.start();if(route.kind==='account-not-found'||route.kind==='not-found')return showNotFound(route.kind==='account-not-found');const state=getLocalProfileState();if(route.kind==='profiles'||route.kind==='profiles-new')profilesView(root(),state,route.kind==='profiles-new');else if(!state.profile) return navigate('/profiles',{replace:true});else if(route.kind==='account-profile')profileView(root(),state.profile);else if(route.kind==='account-bookmarks')await bookmarksView(root(),state.profile);else if(route.kind==='account-settings')settingsView(root(),state.profile);if(id===generation)focus()}
export class Page{static async start(){subscribeLocalProfiles(()=>currentRoute&&render(currentRoute));startRouter(route=>{currentRoute=route;return render(route)})}}

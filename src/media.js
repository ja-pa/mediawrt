/* Translation keys are stable; add languages here without changing UI logic. */
const MW_TEXT = {
  "cs": {
    "request_failed": "Požadavek selhal (",
    "codec": "Prohlížeč tento formát nebo kodek nepřehraje. Soubor můžeš stáhnout nebo otevřít jeho odkaz ve VLC.",
    "count": "Počet videí: ",
    "folder": "Složka",
    "download": "Stáhnout",
    "empty": "Žádná videa pro tento filtr. Nové soubory přidané mimo web načti tlačítkem Obnovit knihovnu.",
    "loading": "Načítám filmy…",
    "items": "Položek: ",
    "videos": " · Videí: ",
    "scanning": " · Aktualizuji knihovnu…",
    "timeout": "Načtení seznamu trvalo příliš dlouho.",
    "retry": " Zkus Obnovit seznam.",
    "loading_folders": "Načítám složky…",
    "folder_error": "Složku nelze otevřít.",
    "parent": "↑ Nadřazená složka",
    "library": "Videotéka",
    "folders": "Složky",
    "movies": "Filmy A–Z",
    "hide_avi": "Skrýt AVI",
    "thumbnails": "Náhledy",
    "group": "Seskupit do složek",
    "size": "Velikost náhledů",
    "small": "Malé",
    "medium": "Střední",
    "large": "Velké",
    "upload": "↑ Nahrát soubory",
    "films": "Filmy",
    "search_hint": "Hledat podle názvu…",
    "search": "Hledat filmy",
    "scan": "Obnovit knihovnu",
    "reload": "Obnovit seznam",
    "pages": "Stránky filmů",
    "previous": "← Předchozí",
    "next": "Další →",
    "groups": "Seskupené složky",
    "back": "← Zpět",
    "all": "Všechny filmy",
    "close": "Zavřít",
    "download_video": "Stáhnout video",
    "destination": "Výběr cílové složky",
    "upload_here": "Nahrát do této složky",
    "choose_destination": "Vyber cílovou složku",
    "favorites": "Oblíbené",
    "history": "Historie",
    "watched": "Zhlédnuto",
    "favorite": "Oblíbené ★",
    "unfavorite": "Odebrat ★",
    "clear": "Vymazat osobní data",
    "clear_confirm": "Vymazat oblíbené i historii tohoto prohlížeče?",
    "local_note": "Oblíbené a historie jsou pouze v tomto prohlížeči. Vymazáním dat prohlížeče o ně přijdeš.",
    "storage_error": "Prohlížeč nedovolil uložit osobní data.",
    "move": "Přesunout / přejmenovat",
    "move_target": "Cílová cesta v knihovně včetně názvu souboru:",
    "move_confirm": "Přesunout následující soubory?",
    "move_failed": "Přesun se nezdařil. Obnov seznam a zkontroluj zdroj i cíl.",
    "move_done": "Přesun dokončen.",
    "index_pending": "Databáze se připravuje. Zkus to za chvíli.",
    "error": "Operace se nezdařila.",
    "language": "Jazyk",
    "subtitles": "Přidat titulky VTT",
    "sort": "Řazení",
    "newest": "Nejnovější",
    "name": "Název A–Z",
    "plan_expired": "Náhled přesunu vypršel. Připrav přesun znovu.",
    "partial_move": "Přesun byl dokončen jen částečně. Zkontroluj uvedené soubory."
  },
  "en": {
    "request_failed": "Request failed (",
    "codec": "This browser cannot play this format or codec. Download it or open its URL in VLC.",
    "count": "Videos: ",
    "folder": "Folder",
    "download": "Download",
    "empty": "No matching videos. Scan the library to discover files added outside the web interface.",
    "loading": "Loading movies…",
    "items": "Items: ",
    "videos": " · Videos: ",
    "scanning": " · Scanning library…",
    "timeout": "The library request timed out.",
    "retry": " Try Reload list.",
    "loading_folders": "Loading folders…",
    "folder_error": "Cannot open folder.",
    "parent": "↑ Parent folder",
    "library": "Media library",
    "folders": "Folders",
    "movies": "Movies A–Z",
    "hide_avi": "Hide AVI",
    "thumbnails": "Thumbnails",
    "group": "Group folders",
    "size": "Thumbnail size",
    "small": "Small",
    "medium": "Medium",
    "large": "Large",
    "upload": "↑ Upload files",
    "films": "Movies",
    "search_hint": "Search by title…",
    "search": "Search movies",
    "scan": "Scan library",
    "reload": "Reload list",
    "pages": "Movie pages",
    "previous": "← Previous",
    "next": "Next →",
    "groups": "Grouped folders",
    "back": "← Back",
    "all": "All movies",
    "close": "Close",
    "download_video": "Download video",
    "destination": "Destination folder",
    "upload_here": "Upload here",
    "choose_destination": "Choose destination folder",
    "favorites": "Favorites",
    "history": "History",
    "watched": "Watched",
    "favorite": "Favorite ★",
    "unfavorite": "Remove ★",
    "clear": "Clear personal data",
    "clear_confirm": "Clear favorites and history in this browser?",
    "local_note": "Favorites and history stay in this browser only. Clearing browser data removes them.",
    "storage_error": "This browser could not save personal data.",
    "move": "Move / rename",
    "move_target": "Destination path within the library, including filename:",
    "move_confirm": "Move these files?",
    "move_failed": "Move failed. Reload and check both source and destination.",
    "move_done": "Move complete.",
    "index_pending": "Index is starting. Try again shortly.",
    "error": "Operation failed.",
    "language": "Language",
    "subtitles": "Add VTT subtitles",
    "sort": "Sort",
    "newest": "Newest",
    "name": "Title A–Z",
    "plan_expired": "Move preview expired. Prepare it again.",
    "partial_move": "Move only partially completed. Check the listed files."
  }
};
/* Media UI for Copyparty 1.20.26. All filenames enter the DOM as text. */
(() => {
    'use strict';
    const API = '/.cpr/media/v1/';
    const $ = (id) => document.getElementById(id);
    const saved = (key, fallback) => { try { return localStorage.getItem('mediawrt.' + key) ?? fallback; } catch (_) { return fallback; } };
    const save = (key, value) => { try { localStorage.setItem('mediawrt.' + key, value); } catch (_) {} };
    let language = saved('language', navigator.language.startsWith('cs') ? 'cs' : 'en');
    const t = key => MW_TEXT[language]?.[key] ?? MW_TEXT.en[key] ?? MW_TEXT.en.error;
    document.documentElement.lang = language;
    let config, page = 0, total = 0, requestId = 0, poll, timer, listController, thumbSession;
    let films = saved('view', 'films') === 'films';
    let hide = saved('hideAvi', '1') === '1';
    let thumbs = saved('thumbs', '1') === '1';
    let size = saved('size', 'medium');
    let grouped = saved('grouped', '0') === '1';
    let folderScope = '', groupHistory = [], personalView = '', sortOrder = 'name', playing = null;
    let personal = {};
    try { personal = JSON.parse(saved('personal.v1', '{}')); if (!personal || Array.isArray(personal) || typeof personal !== 'object') personal = {}; } catch (_) {}
    function persistPersonal() {
        const entries = Object.entries(personal).sort((a,b) => (b[1].at || 0) - (a[1].at || 0)).slice(0,500);
        personal = Object.fromEntries(entries);
        try { localStorage.setItem('mediawrt.personal.v1', JSON.stringify(personal)); }
        catch (_) { message(t('storage_error')); }
    }
    function rememberPosition() {
        const video = $('om-player')?.querySelector('video');
        if (!playing || !video || !Number.isFinite(video.currentTime) || video.currentTime < 1) return;
        personal[playing.id] = {...personal[playing.id], position: video.currentTime, at: Date.now(),
            watched: video.ended || personal[playing.id]?.watched || false};
        persistPersonal();
    }
    async function moveItem(item) {
        const target = prompt(t('move_target'), item.path);
        if (!target || target === item.path) return;
        try {
            const plan = await api('move-preview?' + new URLSearchParams({source: item.path, target}));
            if (!confirm(t('move_confirm') + '\n\n' + plan.files.map(f => f.source + ' → ' + f.target).join('\n'))) return;
            const response = await fetch(API + 'move?' + new URLSearchParams({token: plan.token}),
                {method: 'POST', headers: {'X-Copyparty-Media': '1'}, body: ''});
            const result = await response.json();
            if (!response.ok) throw new Error(t(result.error) + '\n' + (result.completed || []).map(f => f.source + ' → ' + f.target).join('\n'));
            await load(); message(t('move_done'));
        } catch (error) { alert(t('move_failed') + '\n' + error.message); }
    }
    if (!['small', 'medium', 'large'].includes(size)) size = 'medium';

    function el(tag, text, attrs = {}) {
        const node = document.createElement(tag);
        if (text !== null) node.textContent = text;
        for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
        return node;
    }
    function button(text, action) {
        const b = el('button', text, {type: 'button'});
        b.addEventListener('click', action);
        return b;
    }
    async function api(path, scan = false, signal) {
        const response = await fetch(API + path, scan ? {method: 'POST', headers: {'X-Copyparty-Media': '1'}, body: '', signal} : {signal, cache: 'no-store'});
        let data;
        try { data = await response.json(); } catch (_) { throw new Error(t('error') + ' (' + response.status + ')'); }
        if (!response.ok) throw new Error(t(data.error) + ' (' + response.status + ')');
        return data;
    }
    function message(text) { $('om-status').textContent = text; }

    function stopThumbnails() {
        if (!thumbSession) return;
        thumbSession.stopped = true;
        clearTimeout(thumbSession.timer);
        thumbSession.observer.disconnect();
        thumbSession.active.forEach(controller => controller.abort());
        thumbSession.urls.forEach(url => URL.revokeObjectURL(url));
        thumbSession = null;
    }

    function startThumbnails(slots) {
        if (!slots.length) return;
        const session = {stopped: false, active: new Map(), urls: new Set(), timer: null};
        thumbSession = session;
        const tasks = slots.map(([slot, path]) => ({slot, path, visible: false, done: false, next: 0, until: 0}));
        const byElement = new Map(tasks.map(task => [task.slot, task]));
        async function fetchThumbnail(task) {
            const controller = new AbortController();
            session.active.set(task, controller);
            const timeout = setTimeout(() => controller.abort(), 4000);
            try {
                const response = await fetch(API + 'thumbnail?' + new URLSearchParams({path: task.path}),
                    {signal: controller.signal, cache: 'no-store'});
                if (session.stopped) return;
                if (response.status === 200 && response.headers.get('content-type')?.startsWith('image/')) {
                    const blob = await response.blob();
                    if (session.stopped) return;
                    const url = URL.createObjectURL(blob);
                    session.urls.add(url);
                    const image = el('img', null, {src: url, alt: '', decoding: 'async'});
                    image.onload = image.onerror = () => { URL.revokeObjectURL(url); session.urls.delete(url); };
                    task.slot.replaceWith(image);
                    task.done = true;
                } else if (response.status !== 202 && response.status !== 429 && response.status !== 503) task.done = true;
            } catch (_) {
                // Missing/broken/slow previews never become list errors.
            } finally {
                clearTimeout(timeout);
                session.active.delete(task);
                task.next = Date.now() + 2000;
                pump();
            }
        }
        function pump() {
            clearTimeout(session.timer);
            if (session.stopped || document.hidden || !films || !thumbs) return;
            const now = Date.now();
            for (const task of tasks) {
                if (session.active.size >= 2) break;
                if (!task.visible || task.done || session.active.has(task) || task.next > now) continue;
                if (!task.until) task.until = now + 120000;
                if (now > task.until) { task.done = true; continue; }
                fetchThumbnail(task);
            }
            if (session.active.size < 2 && tasks.some(task => task.visible && !task.done)) {
                session.timer = setTimeout(pump, 2000);
            }
        }
        session.observer = new IntersectionObserver(entries => {
            entries.forEach(entry => { byElement.get(entry.target).visible = entry.isIntersecting; });
            pump();
        }, {rootMargin: '100px'});
        tasks.forEach(task => session.observer.observe(task.slot));
    }

    function folderSettings() {
        if ($('om-location')) {
            let path = location.pathname;
            try { path = decodeURIComponent(path); } catch (_) {}
            if ($('om-location').textContent !== path) $('om-location').textContent = path;
        }
        // Do not leave the hidden native gallery fetching blocking thumbnails.
        const nativeThumbs = thumbs && !films;
        if (typeof thegrid !== 'undefined' && thegrid.thumbs !== nativeThumbs && $('thumbs')) $('thumbs').click();
        document.querySelectorAll('#files tbody tr').forEach(row => {
            const a = row.querySelector('td:nth-child(2) a[href]');
            let avi = false;
            try { avi = a && /\.avi$/i.test(decodeURIComponent(new URL(a.href).pathname)); } catch (_) {}
            row.classList.toggle('om-avi-hidden', !!(hide && avi));
        });
        document.querySelectorAll('#ggrid > a').forEach(a => {
            let avi = false;
            try { avi = /\.avi$/i.test(decodeURIComponent(new URL(a.href).pathname)); } catch (_) {}
            a.classList.toggle('om-avi-hidden', !!(hide && avi));
        });
        document.documentElement.style.setProperty('--grid-sz', {small: '9em', medium: '14em', large: '20em'}[size]);
    }

    function setView(value) {
        films = value;
        save('view', films ? 'films' : 'folders');
        document.body.classList.toggle('om-films', films);
        $('om-library').hidden = !films;
        $('om-folders').setAttribute('aria-pressed', String(!films));
        $('om-films').setAttribute('aria-pressed', String(films && !personalView));
        for (const key of ['favorites', 'history']) $('mw-' + key)?.setAttribute('aria-pressed', String(films && personalView === key));
        clearTimeout(poll);
        folderSettings();
        if (films) { $('opa_x')?.click(); load(); }
        else { requestId++; listController?.abort(); stopThumbnails(); }
    }

    function play(item) {
        const dialog = $('om-player');
        const video = dialog.querySelector('video');
        $('om-playing').textContent = item.name;
        $('om-player-error').textContent = '';
        const link = $('om-player-download');
        link.href = item.url + '?dl';
        playing = item;
        video.src = item.url;
        video.onloadedmetadata = () => {
            const position = personal[item.id]?.position || 0;
            if (!personal[item.id]?.watched && position < video.duration - 3) video.currentTime = position;
        };
        video.onerror = () => { $('om-player-error').textContent = t('codec'); };
        dialog.showModal();
        video.play().catch(() => {});
    }

    function render(items) {
        stopThumbnails();
        const slots = [];
        const cards = $('om-cards');
        cards.replaceChildren();
        cards.dataset.size = size;
        cards.classList.toggle('om-text-list', !thumbs);
        for (const item of items) {
            const card = el('article', null, {class: 'om-card'});
            const isFolder = item.kind === 'folder';
            const open = button('', () => {
                if (!isFolder) return play(item);
                groupHistory.push({scope: folderScope, page, query: $('om-search').value});
                folderScope = item.path; page = 0; $('om-search').value = '';
                load(); $('om-library').scrollIntoView({block: 'start'});
            });
            open.className = 'om-open';
            if (isFolder) {
                open.append(el('span', '📁', {class: 'om-folder-icon', 'aria-hidden': 'true'}));
            } else if (thumbs && config.thumbnails) {
                const slot = el('span', '', {class: 'om-placeholder', 'aria-hidden': 'true'});
                open.append(slot);
                slots.push([slot, item.path]);
            }
            open.append(el('span', item.name));
            card.append(open, el('small', item.folder));
            if (isFolder) card.append(el('small', t('count') + item.count));
            const links = el('div', null, {class: 'om-links'});
            const folder = el('a', t('folder'), {href: item.folder_url});
            folder.addEventListener('click', () => save('view', 'folders'));
            links.append(folder);
            if (!isFolder) {
                links.append(el('a', t('download'), {href: item.url + '?dl', download: item.name}));
                const favorite = button(t(personal[item.id]?.favorite ? 'unfavorite' : 'favorite'), () => {
                    const record = personal[item.id] || {};
                    personal[item.id] = {...record, favorite: !record.favorite}; persistPersonal();
                    favorite.textContent = t(personal[item.id].favorite ? 'unfavorite' : 'favorite');
                });
                const watched = button(t('watched'), () => {
                    const record = personal[item.id] || {};
                    personal[item.id] = {...record, watched: !record.watched, at: Date.now()}; persistPersonal();
                    watched.setAttribute('aria-pressed', String(personal[item.id].watched));
                });
                watched.setAttribute('aria-pressed', String(!!personal[item.id]?.watched));
                links.append(favorite, watched);
                if (config.move) links.append(button(t('move'), () => moveItem(item)));
            }
            card.append(links);
            cards.append(card);
        }
        if (!items.length) cards.append(el('p', t('empty')));
        startThumbnails(slots);
    }

    function changePage(delta) {
        if (page + delta < 0 || (page + delta) * 60 >= total) return;
        page += delta;
        load(); $('om-library').scrollIntoView({block: 'start'});
    }

    async function load() {
        if (!films) return;
        const id = ++requestId;
        listController?.abort();
        stopThumbnails();
        const controller = new AbortController();
        listController = controller;
        const timeout = setTimeout(() => controller.abort(), 15000);
        clearTimeout(poll);
        $('om-library').setAttribute('aria-busy', 'true');
        message(t('loading'));
        try {
            const params = new URLSearchParams({page, q: $('om-search').value, hide_avi: hide ? '1' : '0',
                group: grouped && !personalView ? '1' : '0', folder: folderScope, sort: sortOrder});
            if (personalView) params.set('ids', Object.keys(personal).filter(id => personalView === 'favorites' ? personal[id].favorite : personal[id].at).join(','));
            const data = await api('movies?' + params, false, controller.signal);
            if (id !== requestId || !films) return;
            total = data.total;
            if (page && page * data.page_size >= total) { page = 0; return load(); }
            render(data.items);
            for (const suffix of ['', '-top']) {
                $('om-prev' + suffix).disabled = page === 0;
                $('om-next' + suffix).disabled = (page + 1) * data.page_size >= total;
                $('om-page' + suffix).textContent = (page + 1) + ' / ' + Math.max(1, Math.ceil(total / data.page_size));
            }
            $('om-group-nav').hidden = !grouped || !folderScope;
            $('om-group-label').textContent = folderScope;
            $('om-refresh').disabled = data.scanning;
            message((grouped && !personalView ? t('items') + total + t('videos') + data.video_total : t('count') + total) +
                (data.scanning ? t('scanning') : ' · ' + t(sortOrder)));
            if (data.scanning && !document.hidden) poll = setTimeout(load, 3000);
        } catch (error) {
            if (id === requestId && films) {
                message((error.name === 'AbortError' ? t('timeout') : error.message) + t('retry'));
                $('om-refresh').disabled = false;
            }
        } finally {
            clearTimeout(timeout);
            if (id === requestId) $('om-library').setAttribute('aria-busy', 'false');
        }
    }

    async function chooseFolder() {
        const dialog = $('om-upload-dialog');
        const list = $('om-upload-folders');
        let selected = config.volume;
        let serial = 0;
        async function browse(path) {
            const id = ++serial;
            $('om-upload-path').textContent = path;
            $('om-upload-confirm').disabled = true;
            list.replaceChildren(el('p', t('loading_folders')));
            try {
                const response = await fetch(path + '?ls');
                if (!response.ok) throw new Error(t('folder_error'));
                const data = await response.json();
                if (id !== serial) return;
                selected = path;
                list.replaceChildren();
                if (path !== config.volume) {
                    const parent = path.slice(0, -1).slice(0, path.slice(0, -1).lastIndexOf('/') + 1);
                    list.append(button(t('parent'), () => browse(parent)));
                }
                for (const dir of data.dirs || []) {
                    const url = new URL(dir.href, location.origin + path);
                    if (url.origin !== location.origin || !url.pathname.startsWith(config.volume)) continue;
                    list.append(button('📁 ' + decodeURIComponent(url.pathname.slice(path.length).replace(/\/$/, '')), () => browse(url.pathname)));
                }
                $('om-upload-confirm').disabled = !(data.perms || []).includes('write');
            } catch (error) { if (id === serial) list.replaceChildren(el('p', error.message)); }
        }
        $('om-upload-confirm').onclick = () => {
            save('view', 'folders');
            location.href = selected + '#v=up2k';
        };
        dialog.showModal();
        await browse(config.volume);
    }

    async function init() {
        if (!$('files') || $('om-toolbar')) return;
        folderSettings();
        try { config = await api('config'); } catch (_) { return; }
        document.body.classList.add('om-media');
        const toolbar = el('section', null, {id: 'om-toolbar', 'aria-label': t('library')});
        const folders = button(t('folders'), () => setView(false)); folders.id = 'om-folders';
        const movies = button(t('movies'), () => { personalView = ''; page = 0; setView(true); }); movies.id = 'om-films';
        const languageSelect = el('select', null, {'aria-label': t('language')});
        for (const [code, label] of [['cs', 'Čeština'], ['en', 'English']]) languageSelect.append(el('option', label, {value: code}));
        languageSelect.value = language;
        languageSelect.onchange = () => { save('language', languageSelect.value); location.reload(); };
        toolbar.append(el('strong', 'MediaWrt'), el('small', '', {id: 'om-location'}), folders, movies, languageSelect);
        for (const key of ['favorites', 'history']) {
            const choice = button(t(key), () => { personalView = key; page = 0; folderScope = ''; setView(true); });
            choice.id = 'mw-' + key; toolbar.append(choice);
        }
        toolbar.append(button(t('clear'), () => {
            if (confirm(t('clear_confirm'))) { playing = null; personal = {}; persistPersonal(); if (films) load(); }
        }), el('small', t('local_note'), {class: 'mw-note'}));
        function checkbox(id, label, checked, change) {
            const wrap = el('label', null);
            const input = el('input', null, {type: 'checkbox', id}); input.checked = checked;
            input.addEventListener('change', () => change(input.checked));
            wrap.append(input, document.createTextNode(' ' + label)); toolbar.append(wrap);
        }
        checkbox('om-hide', t('hide_avi'), hide, value => { hide = value; save('hideAvi', value ? '1' : '0'); page = 0; folderSettings(); if (films) load(); });
        checkbox('om-thumbs', t('thumbnails'), thumbs, value => { thumbs = value; save('thumbs', value ? '1' : '0'); folderSettings(); if (films) load(); });
        checkbox('om-group', t('group'), grouped, value => {
            grouped = value; save('grouped', value ? '1' : '0');
            folderScope = ''; groupHistory = []; page = 0; if (films) load();
        });
        const select = el('select', null, {'aria-label': t('size')});
        for (const [value, label] of [['small', t('small')], ['medium', t('medium')], ['large', t('large')]]) select.append(el('option', label, {value}));
        select.value = size;
        select.onchange = () => { size = select.value; save('size', size); folderSettings(); $('om-cards').dataset.size = size; };
        toolbar.append(select);
        if (config.upload) toolbar.append(button(t('upload'), () => {
            if (films) chooseFolder();
            else { const b = $('opa_up'); if (b) b.click(); $('op_up2k')?.scrollIntoView({behavior: 'smooth'}); }
        }));
        const library = el('section', null, {id: 'om-library', 'aria-label': t('films')});
        const tools = el('div', null, {class: 'om-library-tools'});
        const search = el('input', null, {id: 'om-search', type: 'search', placeholder: t('search_hint'), 'aria-label': t('search'), maxlength: '200'});
        search.oninput = () => { clearTimeout(timer); timer = setTimeout(() => { page = 0; load(); }, 250); };
        const refresh = button(t('scan'), async () => {
            refresh.disabled = true;
            try { await api('scan', true); page = 0; await load(); }
            catch (error) { message(error.message); refresh.disabled = false; }
        }); refresh.id = 'om-refresh';
        const sorting = el('select', null, {'aria-label': t('sort')});
        for (const key of ['name', 'newest']) sorting.append(el('option', t(key), {value: key}));
        sorting.onchange = () => { sortOrder = sorting.value; grouped = false; $('om-group').checked = false; page = 0; load(); };
        tools.append(search, sorting, button(t('reload'), load), refresh);
        function navigation(suffix) {
            const nav = el('nav', null, {'aria-label': t('pages'), class: 'om-pagination'});
            const prev = button(t('previous'), () => changePage(-1)); prev.id = 'om-prev' + suffix;
            const next = button(t('next'), () => changePage(1)); next.id = 'om-next' + suffix;
            nav.append(prev, el('span', '', {id: 'om-page' + suffix}), next);
            return nav;
        }
        const groupNav = el('nav', null, {id: 'om-group-nav', 'aria-label': t('groups')});
        groupNav.hidden = true;
        groupNav.append(button(t('back'), () => {
            const previous = groupHistory.pop() || {scope: '', page: 0, query: ''};
            folderScope = previous.scope; page = previous.page; $('om-search').value = previous.query; load();
        }), button(t('all'), () => { folderScope = ''; groupHistory = []; page = 0; load(); }),
        el('span', '', {id: 'om-group-label'}));
        library.append(tools, groupNav, el('p', '', {id: 'om-status', role: 'status'}), navigation('-top'),
            el('div', null, {id: 'om-cards'}), navigation(''));
        const wrap = $('wrap'); wrap.prepend(library); wrap.prepend(toolbar);
        const player = el('dialog', null, {id: 'om-player', 'aria-labelledby': 'om-playing'});
        const video = el('video', null, {controls: '', playsinline: '', preload: 'metadata'});
        player.append(button(t('close'), () => player.close()), el('h2', '', {id: 'om-playing'}), video,
            el('p', '', {id: 'om-player-error', role: 'status'}), el('a', t('download_video'), {id: 'om-player-download'}));
        let lastSave = 0;
        video.addEventListener('timeupdate', () => { if (Date.now() - lastSave > 15000) { rememberPosition(); lastSave = Date.now(); } });
        video.addEventListener('pause', rememberPosition);
        video.addEventListener('ended', rememberPosition);
        window.addEventListener('pagehide', rememberPosition);
        let subtitleUrl;
        const subtitleInput = el('input', null, {type: 'file', accept: '.vtt', 'aria-label': t('subtitles')});
        subtitleInput.onchange = () => {
            video.querySelectorAll('track').forEach(track => track.remove());
            if (subtitleUrl) URL.revokeObjectURL(subtitleUrl);
            if (!subtitleInput.files.length) return;
            subtitleUrl = URL.createObjectURL(subtitleInput.files[0]);
            video.append(el('track', null, {kind: 'subtitles', src: subtitleUrl, label: subtitleInput.files[0].name, default: ''}));
        };
        player.append(el('label', t('subtitles')), subtitleInput);
        player.addEventListener('close', () => { rememberPosition(); playing = null; video.pause(); video.removeAttribute('src'); video.load();
            video.querySelectorAll('track').forEach(track => track.remove()); if (subtitleUrl) URL.revokeObjectURL(subtitleUrl); subtitleInput.value = ''; });
        document.body.append(player);
        const upload = el('dialog', null, {id: 'om-upload-dialog', 'aria-label': t('destination')});
        const confirm = button(t('upload_here'), () => {}); confirm.id = 'om-upload-confirm';
        upload.append(button(t('close'), () => upload.close()), el('h2', t('choose_destination')),
            el('p', '', {id: 'om-upload-path'}), el('div', null, {id: 'om-upload-folders'}), confirm);
        document.body.append(upload);
        let scheduled = false;
        const observer = new MutationObserver(() => {
            if (!scheduled) { scheduled = true; requestAnimationFrame(() => { scheduled = false; folderSettings(); }); }
        });
        observer.observe(wrap, {childList: true, subtree: true});
        document.addEventListener('click', event => {
            const a = event.target.closest('#tree a[href], #path a[href], #wfp a[href]');
            if (films && a && !a.getAttribute('href').includes('#') && new URL(a.href).pathname.endsWith('/')) setView(false);
        }, true);
        document.addEventListener('visibilitychange', () => {
            clearTimeout(poll);
            if (document.hidden) stopThumbnails(); else if (films) load();
        });
        window.addEventListener('focus', () => { if (films) load(); });
        setView(films); folderSettings();
    }
    if (document.readyState !== 'loading') init();
    else document.addEventListener('DOMContentLoaded', init, {once: true});
})();

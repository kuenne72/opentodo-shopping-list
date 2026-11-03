// UI texts. To add a language: copy the "en" block, translate, and add the code to LANGS.
// Placeholders: {n}, {name} ... are replaced by tr(key, {n: 3}).
const LANGS = { de: "Deutsch", en: "English" };
const I18N = {
  de: {
    "app.title": "Einkauf",
    "theme.title": "Darstellung: automatisch / hell / dunkel", "theme.aria": "Darstellung wechseln",
    "theme.auto": "Darstellung: automatisch", "theme.light": "Darstellung: hell", "theme.dark": "Darstellung: dunkel",
    "lang.title": "Sprache wechseln",
    "who.title": "Person wechseln", "who.ask": "Wer bist du?",
    "offline": "Keine Verbindung zum Server – Anzeige kann veraltet sein",
    "sub.items": "Artikel", "sub.sections": "Abschnitte", "sub.stores": "Läden", "sub.templates": "Vorlagen", "sub.users": "Personen",
    "nav.list": "Liste", "nav.recent": "Zuletzt", "nav.admin": "Stammdaten",
    "add.placeholder": "z. B. 2 l Milch", "add.aria": "Hinzufügen",
    "all": "Alle",
    "empty.title": "Nichts zu kaufen", "empty.hint": "Unten etwas eintragen, z. B. „2 l Milch“.",
    "no.section": "Ohne Abschnitt", "qty": "Menge", "tick": "Abhaken",
    "done": "Erledigt", "tick.fail": "Konnte nicht abhaken: {msg}", "added": "{name} eingetragen", "error": "Fehler: {msg}",
    "saved": "Gespeichert", "deleted": "Gelöscht", "save": "Speichern", "cancel": "Abbrechen",
    "edit": "Bearbeiten", "delete": "Löschen", "remove": "Entfernen", "name": "Name", "name.missing": "Name fehlt",
    "new.title": "{name} ist neu", "new.q": "In welchen Abschnitt gehört der Artikel?", "new.skip": "Später (bleibt im Standardabschnitt)",
    "cat.open": "Katalog öffnen", "cat.title": "Katalog", "cat.empty": "Noch keine Artikel im Stamm.",
    "cat.seed": "Grundkatalog einspielen (ca. 240 Artikel)", "cat.seeded": "{n} Artikel eingespielt",
    "search": "Suchen…", "none.found": "Nichts gefunden.", "already": "Steht schon auf der Liste",
    "section": "Abschnitt", "store.label": "Laden (keiner = überall)", "store.none": "Keine Läden angelegt",
    "recent.empty": "Noch nichts gekauft", "recent.hint": "Abgehakte Artikel erscheinen hier zum schnellen Wiedereintragen.",
    "templates": "Vorlagen", "n.items": "{n} Artikel", "tpl.apply": "Vorlage auf die Liste", "recent.bought": "Zuletzt gekauft", "re-add": "Wieder eintragen",
    "n.added": "{n} Artikel eingetragen",
    "item.nosec": "kein Abschnitt", "item.also": "auch: {names}", "item.new": "Artikel anlegen", "item.edit": "Artikel bearbeiten",
    "item.seed": "Grundkatalog einspielen", "item.none": "Noch keine Artikel. Grundkatalog einspielen oder Artikel anlegen.",
    "item.imported": "{added} neu, {updated} ergänzt", "item.confirmdel": "Artikel aus dem Stamm löschen?",
    "item.defqty": "Standardmenge", "item.unit": "Einheit", "item.aliases": "Weitere Namen (Komma-getrennt)",
    "item.move": "Offene Einträge in den Abschnitt verschieben", "item.saved": "Gespeichert, {n} Eintrag verschoben",
    "sec.new": "Abschnitt anlegen", "sec.edit": "Abschnitt bearbeiten", "sec.count": "{n} Artikel im Stamm",
    "sec.info": "Abschnitte liegen in OpenTodo (Projekt {project}). Anlegen, Umbenennen, Löschen und die Reihenfolge (gilt in „Alle“) wirken dort; Symbol und Farbe gelten nur hier. Den Laufweg je Laden stellst du unter Läden ein.",
    "sec.confirmdel": "Abschnitt „{name}“ in OpenTodo löschen? Offene Einträge darin verlieren ihren Abschnitt.",
    "sec.look": "Symbol und Farbe",
    "store.new": "Laden anlegen", "store.edit": "Laden bearbeiten", "store.confirmdel": "Laden löschen?",
    "store.sections": "Abschnitte in diesem Laden, in Laufweg-Reihenfolge (Haken = gehört dazu)", "store.min": "Mindestens ein Abschnitt",
    "tpl.new": "Vorlage anlegen", "tpl.confirmdel": "Vorlage löschen?",
    "user.add": "Person hinzufügen",
    "user.info": "Jede Person braucht ein eigenes OpenTodo-Konto und einen API-Token (Zugriff „Voll“).",
    "user.token": "Token", "user.save": "Token speichern", "user.connected": "Verbunden als {name}", "user.confirmdel": "{name} entfernen?",
    "user.none": "Noch keine Personen angelegt.", "user.missing": "Nicht dabei? Jede Person braucht ein eigenes OpenTodo-Konto und einen API-Token.", "user.addnew": "Neue Person hinzufügen",
    "unit.Stk": "Stk", "unit.Pck": "Pck",
    "setup.warn": "Einrichtung unvollständig: Projekt oder Felder in OpenTodo nicht gefunden (siehe Protokoll des Dienstes).",
  },
  en: {
    "app.title": "Shopping",
    "theme.title": "Appearance: automatic / light / dark", "theme.aria": "Change appearance",
    "theme.auto": "Appearance: automatic", "theme.light": "Appearance: light", "theme.dark": "Appearance: dark",
    "lang.title": "Change language",
    "who.title": "Switch person", "who.ask": "Who are you?",
    "offline": "No connection to the server – display may be outdated",
    "sub.items": "Items", "sub.sections": "Sections", "sub.stores": "Stores", "sub.templates": "Templates", "sub.users": "People",
    "nav.list": "List", "nav.recent": "Recent", "nav.admin": "Master data",
    "add.placeholder": "e.g. 2 l milk", "add.aria": "Add",
    "all": "All",
    "empty.title": "Nothing to buy", "empty.hint": "Add something below, e.g. “2 l milk”.",
    "no.section": "No section", "qty": "Qty", "tick": "Check off",
    "done": "Done", "tick.fail": "Could not check off: {msg}", "added": "{name} added", "error": "Error: {msg}",
    "saved": "Saved", "deleted": "Deleted", "save": "Save", "cancel": "Cancel",
    "edit": "Edit", "delete": "Delete", "remove": "Remove", "name": "Name", "name.missing": "Name is missing",
    "new.title": "{name} is new", "new.q": "Which section does this item belong to?", "new.skip": "Later (stays in the default section)",
    "cat.open": "Open catalog", "cat.title": "Catalog", "cat.empty": "No items in the catalog yet.",
    "cat.seed": "Load starter catalog (about 240 items)", "cat.seeded": "{n} items loaded",
    "search": "Search…", "none.found": "Nothing found.", "already": "Already on the list",
    "section": "Section", "store.label": "Store (none = everywhere)", "store.none": "No stores yet",
    "recent.empty": "Nothing bought yet", "recent.hint": "Checked-off items show up here for quick re-adding.",
    "templates": "Templates", "n.items": "{n} items", "tpl.apply": "Add template to list", "recent.bought": "Recently bought", "re-add": "Add again",
    "n.added": "{n} items added",
    "item.nosec": "no section", "item.also": "also: {names}", "item.new": "Add item", "item.edit": "Edit item",
    "item.seed": "Load starter catalog", "item.none": "No items yet. Load the starter catalog or add an item.",
    "item.imported": "{added} new, {updated} updated", "item.confirmdel": "Delete this item from the catalog?",
    "item.defqty": "Default quantity", "item.unit": "Unit", "item.aliases": "Other names (comma separated)",
    "item.move": "Move open entries to this section", "item.saved": "Saved, {n} entry moved",
    "sec.new": "Add section", "sec.edit": "Edit section", "sec.count": "{n} items in the catalog",
    "sec.info": "Sections live in OpenTodo (project {project}). Adding, renaming, deleting and the order (used in “All”) take effect there; icon and color only apply here. The walking order per store is set under Stores.",
    "sec.confirmdel": "Delete section “{name}” in OpenTodo? Open entries in it lose their section.",
    "sec.look": "Icon and color",
    "store.new": "Add store", "store.edit": "Edit store", "store.confirmdel": "Delete this store?",
    "store.sections": "Sections in this store, in walking order (checked = belongs here)", "store.min": "At least one section",
    "tpl.new": "Add template", "tpl.confirmdel": "Delete this template?",
    "user.add": "Add person",
    "user.info": "Each person needs their own OpenTodo account and an API token (access “Full”).",
    "user.token": "Token", "user.save": "Save token", "user.connected": "Connected as {name}", "user.confirmdel": "Remove {name}?",
    "user.none": "No people added yet.", "user.missing": "Not listed? Each person needs their own OpenTodo account and an API token.", "user.addnew": "Add new person",
    "unit.Stk": "pcs", "unit.Pck": "pack",
    "setup.warn": "Setup incomplete: project or custom fields not found in OpenTodo (see the service log).",
  },
};
let LANG = "de";
function pickLang(serverDefault) {
  let l = null;
  try { l = localStorage.getItem("einkauf.lang"); } catch {}
  if (!l || !I18N[l]) l = I18N[serverDefault] ? serverDefault : ((navigator.language || "de").slice(0, 2));
  LANG = I18N[l] ? l : "en";
  return LANG;
}
function tr(key, vars) {
  let s = (I18N[LANG] && I18N[LANG][key]) ?? I18N.en[key] ?? key;
  if (vars) for (const k in vars) s = s.split("{" + k + "}").join(vars[k]);
  return s;
}
function applyI18n() {
  document.documentElement.lang = LANG;
  document.title = tr("app.title");
  document.querySelectorAll("[data-i18n]").forEach(el => { el.textContent = tr(el.dataset.i18n); });
  document.querySelectorAll("[data-i18n-attr]").forEach(el => {
    el.dataset.i18nAttr.split(";").forEach(pair => { const [a, k] = pair.split(":"); el.setAttribute(a, tr(k)); });
  });
}
const unitLabel = u => (u && I18N[LANG] && I18N[LANG]["unit." + u]) || u || "";

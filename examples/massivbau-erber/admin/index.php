<?php
/* Anmeldung und Bearbeitungsansicht */
declare(strict_types=1);
require __DIR__ . '/lib.php';
require __DIR__ . '/page.php';
start_session();

$config = config();
if ($config === null) { header('Location: setup.php'); exit; }

if (!logged_in()) {
    $error = null;
    $wait = locked_seconds();
    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        if ($wait > 0) {
            $error = 'Zu viele Versuche. Bitte in ' . (int) ceil($wait / 60) . ' Minuten noch einmal versuchen.';
        } elseif (!check_csrf($_POST['csrf'] ?? null)) {
            $error = 'Die Sitzung ist abgelaufen. Bitte noch einmal versuchen.';
        } elseif (password_verify((string) ($_POST['password'] ?? ''), $config['password_hash'])) {
            clear_failures();
            session_regenerate_id(true);
            $_SESSION['auth'] = true;
            $_SESSION['csrf'] = bin2hex(random_bytes(32));
            header('Location: index.php');
            exit;
        } else {
            note_failure();
            usleep(600000);
            $error = 'Das Passwort stimmt nicht.';
        }
    } elseif ($wait > 0) {
        $error = 'Zu viele Versuche. Bitte in ' . (int) ceil($wait / 60) . ' Minuten noch einmal versuchen.';
    }
    small_page('Anmelden',
        '<p>Bearbeitungsbereich der Website.</p>'
        . ($error ? '<p class="adm-error" role="alert">' . e($error) . '</p>' : '')
        . '<form method="post">'
        . '<input type="hidden" name="csrf" value="' . e(csrf()) . '">'
        . '<label for="pw">Passwort</label><input id="pw" name="password" type="password" autocomplete="current-password" required autofocus>'
        . '<button type="submit">Anmelden</button></form>'
        . '<p class="adm-small"><a href="../">Zur Website</a></p>');
}

/* ---------- Angemeldet: Seite im Bearbeitungsmodus ausgeben ---------- */
$html = file_get_contents(SITE_FILE);
if ($html === false) { small_page('Fehler', '<p class="adm-error">Die Seite index.html wurde nicht gefunden.</p>'); }

// Ohne das Seitenskript sind alle Folien und Abschnitte gleichzeitig sichtbar und damit bearbeitbar
$html = preg_replace('~<script>document\.documentElement\.classList\.add\(\'js\'\);</script>~', '', $html, 1);
$html = preg_replace('~<script src="script\.js"[^>]*></script>~', '', $html, 1);
$html = preg_replace('~<head>~', "<head>\n  <base href=\"../\">\n  <meta name=\"robots\" content=\"noindex, nofollow\">", $html, 1);

$notice = '';
$messages = [
    'restored' => 'Die Sicherung wurde wiederhergestellt.',
    'password' => 'Das Passwort wurde geändert.',
    'pwerror'  => 'Das Passwort wurde nicht geändert: aktuelles Passwort falsch oder neues Passwort zu kurz (mindestens 12 Zeichen).',
    'error'    => 'Das hat nicht geklappt. Bitte noch einmal versuchen.',
];
if (isset($_GET['msg'], $messages[$_GET['msg']])) { $notice = $messages[$_GET['msg']]; }

$backupItems = '';
foreach (list_backups() as $file) {
    $backupItems .= '<li><span>' . e(backup_label($file)) . '</span>'
        . '<form method="post" action="admin/manage.php"><input type="hidden" name="csrf" value="' . e(csrf()) . '">'
        . '<input type="hidden" name="action" value="restore"><input type="hidden" name="file" value="' . e($file) . '">'
        . '<button type="submit" class="adm-btn adm-btn--ghost">Wiederherstellen</button></form></li>';
}
if ($backupItems === '') { $backupItems = '<li>Noch keine Sicherungen. Vor jedem Speichern wird automatisch eine angelegt.</li>'; }

$csrf = e(csrf());
$cfg = json_encode(['csrf' => csrf(), 'notice' => $notice], JSON_HEX_TAG | JSON_HEX_AMP | JSON_UNESCAPED_UNICODE);
$ui = <<<HTML

<div class="adm-bar" id="adm-bar" role="region" aria-label="Bearbeitungsleiste">
  <p class="adm-bar__title"><strong>Bearbeiten</strong><span id="adm-status" role="status">Keine Änderungen</span></p>
  <div class="adm-bar__actions">
    <button type="button" class="adm-btn adm-btn--primary" id="adm-save" disabled>Speichern</button>
    <button type="button" class="adm-btn" id="adm-discard" disabled>Verwerfen</button>
    <button type="button" class="adm-btn" data-adm-open="adm-backups">Sicherungen</button>
    <button type="button" class="adm-btn" data-adm-open="adm-password">Passwort</button>
    <a class="adm-btn" href="./" target="_blank" rel="noopener" data-adm-link>Seite ansehen</a>
    <form method="post" action="admin/manage.php"><input type="hidden" name="csrf" value="{$csrf}"><input type="hidden" name="action" value="logout"><button type="submit" class="adm-btn">Abmelden</button></form>
  </div>
</div>
<p class="adm-hint" id="adm-hint">Texte anklicken und ändern. Bilder anklicken, um sie zu ersetzen. Danach oben auf „Speichern“ klicken.</p>
<div class="adm-toast" id="adm-toast" role="status" aria-live="polite"></div>

<dialog class="adm-dialog" id="adm-image" aria-labelledby="adm-image-title">
  <h2 id="adm-image-title">Bild ersetzen</h2>
  <img id="adm-image-preview" alt="">
  <label for="adm-image-file">Neues Bild wählen (JPG, PNG oder WebP, höchstens 12 MB)</label>
  <input type="file" id="adm-image-file" accept="image/jpeg,image/png,image/webp">
  <label for="adm-image-alt">Bildbeschreibung (für Suchmaschinen und Vorleseprogramme)</label>
  <input type="text" id="adm-image-alt" maxlength="300">
  <p class="adm-error" id="adm-image-error" role="alert" hidden></p>
  <div class="adm-dialog__actions">
    <button type="button" class="adm-btn adm-btn--primary" id="adm-image-apply">Übernehmen</button>
    <button type="button" class="adm-btn" data-adm-close>Abbrechen</button>
  </div>
</dialog>

<dialog class="adm-dialog" id="adm-backups" aria-labelledby="adm-backups-title">
  <h2 id="adm-backups-title">Sicherungen</h2>
  <p>Vor jedem Speichern wird der vorherige Stand gesichert. Hier lässt sich ein älterer Stand zurückholen.</p>
  <ul class="adm-list">{$backupItems}</ul>
  <div class="adm-dialog__actions"><button type="button" class="adm-btn" data-adm-close>Schließen</button></div>
</dialog>

<dialog class="adm-dialog" id="adm-password" aria-labelledby="adm-password-title">
  <h2 id="adm-password-title">Passwort ändern</h2>
  <form method="post" action="admin/manage.php">
    <input type="hidden" name="csrf" value="{$csrf}"><input type="hidden" name="action" value="password">
    <label for="adm-pw-old">Aktuelles Passwort</label><input id="adm-pw-old" name="current" type="password" autocomplete="current-password" required>
    <label for="adm-pw-new">Neues Passwort (mindestens 12 Zeichen)</label><input id="adm-pw-new" name="password" type="password" autocomplete="new-password" required minlength="12">
    <label for="adm-pw-again">Neues Passwort wiederholen</label><input id="adm-pw-again" name="again" type="password" autocomplete="new-password" required minlength="12">
    <div class="adm-dialog__actions">
      <button type="submit" class="adm-btn adm-btn--primary">Passwort ändern</button>
      <button type="button" class="adm-btn" data-adm-close>Abbrechen</button>
    </div>
  </form>
</dialog>

<link rel="stylesheet" href="admin/editor.css">
<script id="adm-config" type="application/json">{$cfg}</script>
<script src="admin/editor.js"></script>
HTML;

$html = str_replace('</body>', $ui . "\n</body>", $html);
header('Content-Type: text/html; charset=utf-8');
echo $html;

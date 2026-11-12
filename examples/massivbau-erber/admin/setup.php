<?php
/* Einmalige Einrichtung: legt das Passwort fest. Danach ist diese Seite gesperrt. */
declare(strict_types=1);
require __DIR__ . '/lib.php';
require __DIR__ . '/page.php';
start_session();

if (config() !== null) { header('Location: index.php'); exit; }

$error = null;
if (!is_writable(DATA_DIR)) {
    $error = 'Der Ordner admin/data ist nicht beschreibbar. Bitte die Schreibrechte beim Hoster prüfen.';
} elseif ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!check_csrf($_POST['csrf'] ?? null)) {
        $error = 'Die Sitzung ist abgelaufen. Bitte noch einmal versuchen.';
    } else {
        $pw = (string) ($_POST['password'] ?? '');
        $error = password_problem($pw, (string) ($_POST['again'] ?? ''));
        if ($error === null) {
            if (save_config(password_hash($pw, PASSWORD_DEFAULT))) {
                session_regenerate_id(true);
                $_SESSION['auth'] = true;
                header('Location: index.php');
                exit;
            }
            $error = 'Das Passwort konnte nicht gespeichert werden.';
        }
    }
}

small_page('Zugang einrichten',
    '<p>Legen Sie das Passwort für den Bearbeitungsbereich fest. Mindestens 12 Zeichen.</p>'
    . ($error ? '<p class="adm-error" role="alert">' . e($error) . '</p>' : '')
    . '<form method="post" autocomplete="off">'
    . '<input type="hidden" name="csrf" value="' . e(csrf()) . '">'
    . '<label for="pw">Passwort</label><input id="pw" name="password" type="password" autocomplete="new-password" required minlength="12">'
    . '<label for="pw2">Passwort wiederholen</label><input id="pw2" name="again" type="password" autocomplete="new-password" required minlength="12">'
    . '<button type="submit">Zugang anlegen</button></form>');

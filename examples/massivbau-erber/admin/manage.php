<?php
/* Abmelden, Sicherung wiederherstellen, Passwort ändern */
declare(strict_types=1);
require __DIR__ . '/lib.php';
start_session();

function back(string $msg = ''): never {
    header('Location: index.php' . ($msg ? '?msg=' . $msg : ''));
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST' || !logged_in() || !check_csrf($_POST['csrf'] ?? null)) { back(); }

switch ($_POST['action'] ?? '') {
    case 'logout':
        $_SESSION = [];
        session_regenerate_id(true);
        back();

    case 'restore':
        $file = (string) ($_POST['file'] ?? '');
        if (!in_array($file, list_backups(), true)) { back('error'); }
        $content = file_get_contents(BACKUP_DIR . '/' . $file);
        if ($content === false || !str_contains($content, '</html>')) { back('error'); }
        if (!make_backup() || !write_atomic(SITE_FILE, $content)) { back('error'); }
        back('restored');

    case 'password':
        $config = config();
        $pw = (string) ($_POST['password'] ?? '');
        if (!$config || !password_verify((string) ($_POST['current'] ?? ''), $config['password_hash'])
            || password_problem($pw, (string) ($_POST['again'] ?? '')) !== null) {
            usleep(600000);
            back('pwerror');
        }
        if (!save_config(password_hash($pw, PASSWORD_DEFAULT))) { back('error'); }
        session_regenerate_id(true);
        back('password');
}
back();

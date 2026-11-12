<?php
/* Speichert geänderte Texte und Bilder in die index.html (mit Sicherung davor) */
declare(strict_types=1);
require __DIR__ . '/lib.php';
start_session();
require_login();

if ($_SERVER['REQUEST_METHOD'] !== 'POST') { json_out(['ok' => false, 'error' => 'Nicht erlaubt.'], 405); }
$in = json_decode((string) file_get_contents('php://input'), true);
if (!is_array($in) || !check_csrf($in['csrf'] ?? null)) {
    json_out(['ok' => false, 'error' => 'Die Sitzung ist abgelaufen. Bitte die Seite neu laden.'], 403);
}

$html = file_get_contents(SITE_FILE);
if ($html === false) { json_out(['ok' => false, 'error' => 'Die Seite konnte nicht gelesen werden.'], 500); }
$before = $html;
$done = 0;
$skipped = [];

foreach ((array) ($in['texts'] ?? []) as $key => $text) {
    if (!is_string($key) || !preg_match('/^[a-z0-9-]{1,60}$/', $key) || !is_string($text)) { continue; }
    if (mb_strlen($text) > MAX_TEXT_LENGTH) { $skipped[] = $key; continue; }
    $safe = clean_text($text);
    if ($safe === '') { $skipped[] = $key; continue; }
    if (set_text($html, $key, $safe) > 0) { $done++; } else { $skipped[] = $key; }
}

foreach ((array) ($in['images'] ?? []) as $key => $img) {
    if (!is_string($key) || !preg_match('/^img-[a-z0-9-]{1,60}$/', $key) || !is_array($img)) { continue; }
    $src = null; $w = null; $h = null;
    if (isset($img['src'])) {
        $src = (string) $img['src'];
        if (!preg_match('~^assets/uploads/[a-z0-9-]+\.(jpg|png|webp)$~', $src)) { $skipped[] = $key; continue; }
        $path = __DIR__ . '/../' . $src;
        $size = is_file($path) ? @getimagesize($path) : false;
        if (!$size) { $skipped[] = $key; continue; }
        [$w, $h] = [$size[0], $size[1]];
    }
    $alt = isset($img['alt']) && is_string($img['alt']) ? trim(mb_substr(preg_replace('/\s+/u', ' ', $img['alt']) ?? '', 0, 300)) : null;
    if (set_image($html, $key, $src, $alt, $w, $h) > 0) { $done++; } else { $skipped[] = $key; }
}

foreach ((array) ($in['groups'] ?? []) as $name => $items) {
    if (!is_string($name) || !is_array($items)) { continue; }
    $problem = rebuild_group($html, $name, array_values($items));
    if ($problem !== null) { json_out(['ok' => false, 'error' => $problem . ' Es wurde nichts gespeichert.'], 422); }
    $done++;
}

if ($html === $before) {
    json_out(['ok' => true, 'saved' => 0, 'skipped' => $skipped]);
}
if (!str_contains($html, '</html>') || strlen($html) < strlen($before) * 0.5) {
    json_out(['ok' => false, 'error' => 'Die Änderung wurde zur Sicherheit nicht gespeichert.'], 422);
}
if (!make_backup()) { json_out(['ok' => false, 'error' => 'Die Sicherung konnte nicht angelegt werden. Es wurde nichts geändert.'], 500); }
if (!write_atomic(SITE_FILE, $html)) { json_out(['ok' => false, 'error' => 'Die Seite konnte nicht geschrieben werden.'], 500); }

json_out(['ok' => true, 'saved' => $done, 'skipped' => $skipped]);

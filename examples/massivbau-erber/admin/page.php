<?php
/* Einfache Rahmenseite für Anmeldung und Einrichtung */
declare(strict_types=1);

function small_page(string $title, string $body): never {
    header('Content-Type: text/html; charset=utf-8');
    echo '<!doctype html><html lang="de"><head><meta charset="utf-8">'
       . '<meta name="viewport" content="width=device-width, initial-scale=1">'
       . '<meta name="robots" content="noindex, nofollow">'
       . '<title>' . e($title) . ' · Massivbau Erber</title>'
       . '<link rel="stylesheet" href="editor.css"></head>'
       . '<body class="adm-plain"><main class="adm-box">'
       . '<p class="adm-brand">ERBER <span>MASSIVBAU</span></p>'
       . '<h1>' . e($title) . '</h1>' . $body . '</main></body></html>';
    exit;
}

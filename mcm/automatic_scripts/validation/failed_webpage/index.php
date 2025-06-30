<?php
// Get all the request prepids' by scanning the folders
// This is how they're stored.
function get_request_folders($base_path) {
    $folders = [];

    foreach (scandir($base_path) as $entry) {
        if ($entry === '.' || $entry === '..') continue;
        $full_path = $base_path . DIRECTORY_SEPARATOR . $entry;
        $timezone = new DateTimeZone('Europe/Zurich');
        if (is_dir($full_path)) {
            $datetime = new DateTime();
            $datetime->setTimestamp(filectime($full_path));
            $datetime->setTimeZone($timezone);
            $folders[] = [
                'prepid' => $entry,
                'created' => $datetime->format('Y-m-d H:i:s T'),
            ];
        }
    }

    usort($folders, fn($a, $b) => strcmp($b['created'], $a['created'])); // sort newest first
    return $folders;
}

$base_path = __DIR__;
$request_folders = get_request_folders($base_path);
?>
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no" />
    <link rel="icon" href="favicon.png" />
    <link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Roboto:100,300,400,500,700,900" />
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css"
      integrity="sha384-ggOyR0iXCbMQv3Xipma34MD+dH/1fQ784/j6cY/iJTQUOhcWr7x9JvoRxT2MZw1T" crossorigin="anonymous" />
    <link rel="stylesheet" type="text/css" href="style.css" />
    <script src="https://code.jquery.com/jquery-3.4.1.min.js"
      integrity="sha256-CSXorXvZcTkaix6Yvo6HppcZGetbYMGWSFlBw8HfCJo=" crossorigin="anonymous"></script>
    <title>McM Validation Reports</title>
  </head>
  <body>
    <header class="v-sheet v-sheet--tile theme--light v-toolbar v-app-bar v-app-bar--fixed elevation-3"
      data-booted="true" style="height: 64px; margin-top: 0px; transform: translateY(0px); left: 0px; right: 0px; position: fixed; z-index: 999;">
      <div class="v-toolbar__content" style="height: 64px">
        <a href="/" style="text-decoration: none; color: rgba(0, 0, 0, 0.87)">
          <div class="headline">
            <span>McM</span> <span class="font-weight-light">Validation</span>
          </div>
        </a>
        <div style="margin-left: auto; padding-right: 16px; font-weight: 500">
          <span class="font-weight-light">
            This folder includes execution records for failed validations. They
            could be useful for you to debug the parameters for validating your
            requests!
          </span>
        </div>
      </div>
    </header>
    <div class="container-fluid"
      style="padding: 76px 12px 12px 12px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.5rem;">
      <?php foreach ($request_folders as $request): ?>
      <div class="card mt-2 elevation-3" style="width: 100%; box-sizing: border-box">
        <div class="card-body" style="width: 100%; box-sizing: border-box; padding: 1rem">
          <a href="<?= htmlspecialchars($request['prepid']) ?>" class="bigger-text" id="<?= htmlspecialchars($request['prepid']) ?>">
            <?= htmlspecialchars($request['prepid']) ?>
          </a>
          <br />
          <span>
            <span class="font-weight-light">Created:</span>
            <?= htmlspecialchars($request['created']) ?>
          </span>
          <br />
        </div>
      </div>
      <?php endforeach; ?>
    </div>
  </body>
</html>

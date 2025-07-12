<?php
header('Content-Type: application/json');
require 'db_connect.php';

$start = $_GET['start'] ?? null;
$end = $_GET['end'] ?? null;
$limit = $_GET['limit'] ?? 20;

try {
    $query = "SELECT * FROM log_data";
    $conditions = [];

    if ($start) {
        $conditions[] = "timestamp >= '$start'";
    }
    if ($end) {
        $conditions[] = "timestamp <= '$end'";
    }

    if (count($conditions) > 0) {
        $query .= " WHERE " . implode(" AND ", $conditions);
    }

    $query .= " ORDER BY timestamp DESC LIMIT " . intval($limit);

    $stmt = $pdo->query($query);
    $logs = $stmt->fetchAll(PDO::FETCH_ASSOC);
    echo json_encode($logs);
} catch (PDOException $e) {
    echo json_encode(['error' => $e->getMessage()]);
}
?>

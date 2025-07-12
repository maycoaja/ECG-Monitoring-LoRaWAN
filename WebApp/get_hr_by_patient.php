<?php
header('Content-Type: application/json');
require 'db_connect.php';

$id = $_GET['id'] ?? null;

if (!$id) {
    http_response_code(400);
    echo json_encode(['error' => 'No patient ID']);
    exit;
}

try {
    $stmt = $pdo->prepare("SELECT timestamp, bpm FROM heart_rate WHERE patient_id = ? ORDER BY timestamp DESC LIMIT 50");
    $stmt->execute([$id]);
    $hrData = $stmt->fetchAll(PDO::FETCH_ASSOC);
    echo json_encode($hrData);
} catch (PDOException $e) {
    echo json_encode(['error' => $e->getMessage()]);
}
?>

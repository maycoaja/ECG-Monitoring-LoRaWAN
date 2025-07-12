<?php
header('Content-Type: application/json');
require 'db_connect.php';

try {
    $stmt = $pdo->query("
        SELECT 
            p.*,
            (
                SELECT MAX(timestamp)
                FROM heart_rate
                WHERE patient_id = p.id
            ) AS last_update
        FROM patients p
        ORDER BY p.id ASC
    ");
    $patients = $stmt->fetchAll(PDO::FETCH_ASSOC);
    echo json_encode($patients);
} catch (PDOException $e) {
    echo json_encode(['error' => $e->getMessage()]);
}
?>

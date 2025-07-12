<?php
require 'db_connect.php';

$patientId = $_GET['id'] ?? null;
if (!$patientId) {
    die("No patient ID");
}

header("Content-Type: text/csv");
header("Content-Disposition: attachment; filename=patient_$patientId.csv");

$output = fopen("php://output", "w");

// Header CSV
fputcsv($output, ['Timestamp', 'Heart Rate', 'ECG Value']);

$query = "
    SELECT 
        COALESCE(hr.timestamp, ecg.timestamp) AS timestamp,
        hr.bpm,
        ecg.value AS ecg_value
    FROM
        heart_rate hr
    FULL OUTER JOIN
        ecg_data ecg ON hr.patient_id = ecg.patient_id AND hr.timestamp = ecg.timestamp
    WHERE
        hr.patient_id = :id OR ecg.patient_id = :id
    ORDER BY timestamp DESC
";

$stmt = $pdo->prepare($query);
$stmt->execute(['id' => $patientId]);

while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
    fputcsv($output, [$row['timestamp'], $row['bpm'], $row['ecg_value']]);
}

fclose($output);
exit;

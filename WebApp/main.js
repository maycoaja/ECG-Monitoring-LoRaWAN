/** main.js Final Konsep Device Fix **/

let selectedPatientId = null;
let selectedPatient = null;
let hrChart = null;
let currentSlot = null;

document.addEventListener("DOMContentLoaded", () => {
    const toggleButton = document.getElementById("toggleSidebar");
    const sidebar = document.querySelector(".sidebar");

    if (toggleButton) {
        toggleButton.addEventListener("click", () => {
            sidebar.classList.toggle("collapsed");
        });
    }
});

function login() {
    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;

    if (!username || !password) {
        alert("Masukkan username dan password");
        return;
    }

    fetch("login.php", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
    })
        .then(res => res.json())
        .then(data => {
            if (data.status === "success") {
                document.getElementById("login-screen").style.display = "none";
                document.getElementById("main-app").style.display = "block";
                loadDashboardPatients();
            } else {
                alert("Login gagal: " + (data.message || "Coba lagi"));
            }
        })
        .catch(err => {
            console.error(err);
            alert("Terjadi kesalahan koneksi.");
        });
}

function logout() {
    document.getElementById("main-app").style.display = "none";
    document.getElementById("login-screen").style.display = "flex";
}

const sectionTitles = {
    dashboard: "Dashboard",
    patients: "Daftar Pasien",
    log: "Log Data ECG",
    'patient-detail': "Detail Pasien"
};

function showSection(section) {
    const title = sectionTitles[section] || section;
    document.getElementById('section-title').innerText = title;

    ['dashboard-section', 'patients-section', 'log-section', 'patient-detail-section'].forEach(id =>
        document.getElementById(id).classList.add('hidden')
    );

    document.getElementById(`${section}-section`).classList.remove('hidden');

    if (section === 'patients') loadPatients();
    if (section === 'dashboard') loadDashboardPatients();
}

function initChart(labels, data) {
    const ctx = document.getElementById('hrCanvas').getContext('2d');
    if (hrChart) hrChart.destroy();
    hrChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Heart Rate (BPM)',
                data: data,
                borderColor: '#e74c3c',
                backgroundColor: 'rgba(231, 76, 60, 0.2)',
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: false },
            scales: { y: { beginAtZero: true } }
        }
    });
}

function loadDashboardPatients() {
    fetch('get_patients.php')
        .then(res => res.json())
        .then(data => {
            const deviceMap = {
                "mayco-ekg": { name: "Device Off", hr: "--", patient: null },
                "mayco-ekg2": { name: "Device Off", hr: "--", patient: null },
                "mayco-ekg3": { name: "Device Off", hr: "--", patient: null }
            };

            data.forEach(p => {
                if (deviceMap[p.device_id]) {
                    deviceMap[p.device_id] = {
                        name: p.name || "Unknown",
                        hr: p.heart_rate ?? "--",
                        patient: p
                    };
                }
            });

            // Update tampilan kotak dashboard
            document.getElementById("d1-name").innerText = deviceMap["mayco-ekg"].name;
            document.getElementById("d1-hr").innerText = `${deviceMap["mayco-ekg"].hr} BPM`;
            document.getElementById("d2-name").innerText = deviceMap["mayco-ekg2"].name;
            document.getElementById("d2-hr").innerText = `${deviceMap["mayco-ekg2"].hr} BPM`;
            document.getElementById("d3-name").innerText = deviceMap["mayco-ekg3"].name;
            document.getElementById("d3-hr").innerText = `${deviceMap["mayco-ekg3"].hr} BPM`;

            // === AUTO TAMPILKAN GRAFIK PERTAMA YANG TERISI ===
            const firstAvailable = Object.values(deviceMap).find(d => d.patient);
            if (firstAvailable) {
                updateChartForPatient(firstAvailable.patient);
            } else {
                console.log("[Dashboard] Tidak ada pasien aktif saat ini.");
            }
        });
}



function showPatientByDevice(deviceId) {
    fetch('get_patients.php')
        .then(res => res.json())
        .then(patients => {
            const patient = patients.find(p => p.device_id === deviceId);
            if (!patient) {
                alert("Device belum terdaftar ke pasien.");
                return;
            }

            fetch(`get_hr_by_patient.php?id=${patient.id}`)
                .then(res => res.json())
                .then(hrData => {
                    if (hrData.length === 0) {
                        alert("Belum ada data HR untuk pasien ini.");
                        return;
                    }

                    const labels = hrData.map(d => d.timestamp);
                    const values = hrData.map(d => d.bpm);
                    initChart(labels, values); // tampilkan grafik di dashboard
                });
        });
}

function showPatientBySlot(slotNumber) {
    currentSlot = slotNumber;

    fetch("get_patients.php")
        .then(res => res.json())
        .then(data => {
            const found = data.find(p => p.slot_number == slotNumber);
            if (found) {
                openDetail(found);
            } else {
                openEmptyDetail("-");
            }
        });
}

function showPatientSection(slotNumber) {
    // Sembunyikan semua section dulu
    ['dashboard-section', 'patients-section', 'log-section', 'patient-detail-section'].forEach(id =>
        document.getElementById(id).classList.add('hidden')
    );

    document.getElementById('section-title').innerText = sectionTitles["patient-detail"];
    document.getElementById('patient-detail-section').classList.remove('hidden');

    // Reset isi kosong dulu
    selectedPatientId = null;
    selectedPatient = null;

    document.getElementById("d-name").innerText = "-";
    document.getElementById("d-age").innerText = "-";
    document.getElementById("d-gender").innerText = "-";
    document.getElementById("d-mrn").innerText = "-";
    document.getElementById("d-device").innerText = "-";
    document.getElementById("d-condition").innerText = "-";
    document.getElementById("d-notes").innerText = "-";
    document.getElementById("d-hr").innerText = "--";

    const statusEl = document.getElementById("d-status");
    statusEl.innerText = "Offline";
    statusEl.className = "offline";

    if (window.hrChart) window.hrChart.destroy();
    if (window.ecgChart) window.ecgChart.destroy();

    document.querySelector(".stop-btn").style.display = "none";
    document.querySelector(".download-btn").style.display = "none";

}

function openEmptyDetail(deviceId) {
    document.getElementById('section-title').innerText = "Detail Pasien";
    ['dashboard-section', 'patients-section', 'log-section', 'patient-detail-section'].forEach(id =>
        document.getElementById(id).classList.add('hidden')
    );
    document.getElementById('patient-detail-section').classList.remove('hidden');

    const fields = ["name", "age", "gender", "mrn", "device", "condition", "notes", "hr"];
    fields.forEach(f => {
        document.getElementById(`d-${f}`).innerText = (f === "hr") ? "--" : "-";
    });

    const statusEl = document.getElementById("d-status");
    statusEl.innerText = "Belum ada data";
    statusEl.className = "";

    selectedPatientId = null;
    selectedPatient = null;

    if (window.hrChart) window.hrChart.destroy();
    if (window.ecgChart) window.ecgChart.destroy();

    document.querySelectorAll(".stop-btn").forEach(btn => btn.classList.add("hidden"));
    document.querySelectorAll(".download-btn").forEach(btn => btn.classList.add("hidden"));
}

function openModal() {
    // Reset field
    document.getElementById("modal-name").value = selectedPatient?.name || "";
    document.getElementById("modal-age").value = selectedPatient?.age || "";
    document.getElementById("modal-gender").value = selectedPatient?.gender || "";
    document.getElementById("modal-mrn").value = selectedPatient?.mrn || "";
    document.getElementById("modal-condition").value = selectedPatient?.condition || "";
    document.getElementById("modal-notes").value = selectedPatient?.notes || "";
    document.getElementById("modal-device").value = selectedPatient?.device_id || "";
    document.getElementById("modal-slot").value = currentSlot || "";

    fetch('get_patients.php')
        .then(res => res.json())
        .then(data => {
            const usedDevices = data
                .filter(p => !selectedPatient || p.id !== selectedPatient.id)
                .map(p => p.device_id);

            const select = document.getElementById("modal-device");
            [...select.options].forEach(opt => {
                if (opt.value === "") return;
                opt.disabled = usedDevices.includes(opt.value);
            });

            document.getElementById("addModal").style.display = "flex";
        });

}

function closeModal() {
    document.getElementById("addModal").style.display = "none";
}

function loadPatients() {
    fetch('get_patients.php')
        .then(res => res.json())
        .then(data => {
            const grid = document.getElementById("patient-grid-db");
            grid.innerHTML = "";
            data.forEach(p => {
                const card = document.createElement("div");
                card.className = "patient-card";
                card.innerHTML = `<div class="patient-name">${p.name}</div><div class="bpm">${p.heart_rate ?? '-'} BPM</div>`;
                card.onclick = () => openDetail(p);
                grid.appendChild(card);
            });
        });
}

function openDetail(p) {
    selectedPatientId = p.id;
    selectedPatient = p;

    // Ganti section
    ['dashboard-section', 'patients-section', 'log-section', 'patient-detail-section'].forEach(id =>
        document.getElementById(id).classList.add('hidden')
    );
    document.getElementById('section-title').innerText = p.name || "Patient";
    document.getElementById('patient-detail-section').classList.remove('hidden');

    // MASUKKAN ISI DATA PASIEN KE TAMPILAN
    document.getElementById("d-name").innerText = p.name || "-";
    document.getElementById("d-age").innerText = p.age || "-";
    document.getElementById("d-gender").innerText = p.gender || "-";
    document.getElementById("d-mrn").innerText = p.mrn || "-";
    document.getElementById("d-device").innerText = p.device_id || "-";
    document.getElementById("d-condition").innerText = p.condition || "-";
    document.getElementById("d-notes").innerText = p.notes || "-";
    document.getElementById("d-hr").innerText = p.heart_rate ? `${p.heart_rate} BPM` : "--";

    // STATUS DEVICE: last update
    const lastUpdate = p.last_update ? new Date(p.last_update) : null;
    const statusEl = document.getElementById("d-status");

    if (lastUpdate && !isNaN(lastUpdate)) {
        statusEl.innerText = `${p.last_update}`;
        statusEl.className = "";
    } else {
        statusEl.innerText = "Belum ada data";
        statusEl.className = "";
    }

    // Load grafik
    updateHrHistoryChart(p.id);
    updateEcgRawChart(p.id);

    // TAMPILKAN tombol
    document.querySelectorAll(".stop-btn").forEach(btn => btn.classList.remove("hidden"));
    document.querySelectorAll(".download-btn").forEach(btn => btn.classList.remove("hidden"));
}


function updateHrHistoryChart(patientId) {
    fetch(`get_hr_by_patient.php?id=${patientId}`)
        .then(res => res.json())
        .then(data => {
            const ctx = document.getElementById("hrHistoryChart").getContext("2d");
            if (window.hrChart) window.hrChart.destroy();
            window.hrChart = new Chart(ctx, {
                type: "line",
                data: {
                    labels: data.map(d => d.timestamp),
                    datasets: [{
                        label: "Heart Rate",
                        data: data.map(d => d.bpm),
                        borderColor: "#e74c3c",
                        fill: false,
                        tension: 0.3
                    }]
                }
            });
        });
}

function updateEcgRawChart(patientId) {
    fetch(`get_ecg_by_patient.php?id=${patientId}`)
        .then(res => res.json())
        .then(data => {
            const ctx = document.getElementById("ecgRawChart").getContext("2d");
            if (window.ecgChart) window.ecgChart.destroy();
            window.ecgChart = new Chart(ctx, {
                type: "line",
                data: {
                    labels: data.map((_, i) => i),
                    datasets: [{
                        label: "ECG Raw Signal",
                        data: data,
                        borderColor: "#2c3e50",
                        fill: false,
                        tension: 0
                    }]
                }
            });
        });
}

function stopMonitoring() {
    if (!selectedPatientId) return;

    const confirmStop = confirm("Yakin ingin menghentikan pemantauan pasien ini?");
    if (!confirmStop) return;

    fetch(`delete_patient.php?id=${selectedPatientId}`)
        .then(res => res.json())
        .then(data => {
            if (data.status === "success") {
                alert("Pasien telah dihapus dari pemantauan.");
                selectedPatientId = null;
                selectedPatient = null;

                resetPatientDetail(); // ini penting banget!
                showSection("patients"); // balik ke daftar pasien
            } else {
                alert("Gagal menghapus pasien: " + data.message);
            }
        })
        .catch(err => {
            alert("Terjadi kesalahan saat menghapus.");
            console.error(err);
        });
}

function resetPatientDetail() {
    const fields = ["name", "age", "gender", "mrn", "device", "condition", "notes", "hr"];
    fields.forEach(f => {
        document.getElementById(`d-${f}`).innerText = (f === "hr") ? "--" : "-";
    });

    document.querySelectorAll("#d-status").forEach(el => {
        el.innerText = "Belum ada data";
        el.className = "";
    });

    selectedPatientId = null;
    selectedPatient = null;

    // Hapus grafik
    if (window.hrChart) {
        window.hrChart.destroy();
        window.hrChart = null;
    }
    if (window.ecgChart) {
        window.ecgChart.destroy();
        window.ecgChart = null;
    }

    // Sembunyikan tombol
    document.querySelectorAll(".stop-btn").forEach(btn => btn.classList.add("hidden"));
    document.querySelectorAll(".download-btn").forEach(btn => btn.classList.add("hidden"));
}

function downloadData() {
    alert("Data pasien siap diunduh.");
}

function closeDetail() {
    document.getElementById("detailModal").style.display = "none";
}

function editPatient() {
    document.getElementById("modal-name").value = selectedPatient?.name || "";
    document.getElementById("modal-age").value = selectedPatient?.age || "";
    document.getElementById("modal-gender").value = selectedPatient?.gender || "";
    document.getElementById("modal-device").value = selectedPatient?.device_id || "";
    document.getElementById("modal-notes").value = selectedPatient?.notes || "";
    document.getElementById("modal-slot").value = selectedPatient?.slot_number || currentSlot || "";

    document.getElementById("addModal").style.display = "flex";
}

function submitPatient() {
    const name = document.getElementById("modal-name").value;
    const age = document.getElementById("modal-age").value;
    const gender = document.getElementById("modal-gender").value;
    const deviceId = document.getElementById("modal-device").value;
    const notes = document.getElementById("modal-notes").value;
    const mrn = document.getElementById("modal-mrn").value;
    const condition = document.getElementById("modal-condition").value;
    const slotNumber = document.getElementById("modal-slot").value;

    const payload = {
        id: selectedPatient?.id || null,
        name, age, gender, device_id: deviceId, notes, mrn, condition, slot_number: slotNumber
    };

    fetch("save_patient.php", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    })
        .then(res => res.json())
        .then(data => {
            if (data.status === "success") {
                fetch("get_patients.php")
                    .then(res => res.json())
                    .then(allPatients => {
                        const updated = allPatients.find(p => p.id === data.id);
                        if (updated) {
                            selectedPatient = updated;
                            selectedPatientId = updated.id;
                            openDetail(updated);
                        }
                        closeModal();
                        showPatientBySlot(slotNumber);
                    });
            } else {
                alert("Gagal menyimpan data: " + (data.message || "Unknown error"));
            }
        })
        .catch(err => {
            console.error(err);
            alert("Terjadi kesalahan.");
        });
}

function loadLogData() {
    const start = document.getElementById("log-start").value;
    const end = document.getElementById("log-end").value;
    const limit = document.getElementById("log-limit").value;

    fetch(`get_log_data.php?start=${start}&end=${end}&limit=${limit}`)
        .then(res => res.json())
        .then(data => {
            const tbody = document.getElementById("log-body");
            tbody.innerHTML = "";
            data.forEach((log, index) => {
                const row = document.createElement("tr");
                row.innerHTML = `
          <td>${index + 1}</td>
          <td>${log.timestamp}</td>
          <td>${log.device_id}</td>
          <td>${log.type}</td>
          <td>${log.value}</td>
        `;
                tbody.appendChild(row);
            });
        });
}

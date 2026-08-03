// ==========================================
// KONFIGURASI KREDENSIAL
// ==========================================
var CARTRACK_USER = "PROY00001";
var CARTRACK_PASS = "83e18c5ea077615626fbc9c5f9566e5b6ae45c00a7b6fcfc6bd2562cdb86bd6d";
var CARTRACK_BASE_URL = "https://fleetapi-id.cartrack.com/rest/vehicles";

var ODOO_URL     = "https://proyekin.odoo.com";  
var ODOO_DB      = "proyekin";                   
var ODOO_USER    = "lucky@proyekin.co.id";  
var Odoo_API_KEY = "0c43226f9769cde2ce5d92ac5993897e2876d19e";

// ==========================================
// FUNGSI BANTUAN ODOO (JSON-RPC)
// ==========================================
function getOdooUid() {
  var payload = {
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "service": "common",
      "method": "authenticate",
      "args": [ODOO_DB, ODOO_USER, Odoo_API_KEY, {}]
    },
    "id": 1
  };
  var options = {
    "method": "post",
    "contentType": "application/json",
    "payload": JSON.stringify(payload),
    "muteHttpExceptions": true
  };
  var res = UrlFetchApp.fetch(ODOO_URL + "/jsonrpc", options);
  var json = JSON.parse(res.getContentText());
  return json.result;
}

function odooSearch(uid, model, domain) {
  var payload = {
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "service": "object",
      "method": "execute_kw",
      "args": [ODOO_DB, uid, Odoo_API_KEY, model, "search", [domain]]
    },
    "id": 2
  };
  var options = {
    "method": "post",
    "contentType": "application/json",
    "payload": JSON.stringify(payload),
    "muteHttpExceptions": true
  };
  var res = UrlFetchApp.fetch(ODOO_URL + "/jsonrpc", options);
  var json = JSON.parse(res.getContentText());
  var result = json.result;
  return (result && result.length > 0) ? result[0] : null;
}

function kirimOdometerKeOdoo(uid, vehicleId, value, dateStr) {
  var payload = {
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "service": "object",
      "method": "execute_kw",
      "args": [ODOO_DB, uid, Odoo_API_KEY, "fleet.vehicle.odometer", "create", [{
        "vehicle_id": vehicleId,
        "value": Number(value),
        "date": dateStr
      }]]
    },
    "id": 3
  };
  var options = {
    "method": "post",
    "contentType": "application/json",
    "payload": JSON.stringify(payload),
    "muteHttpExceptions": true
  };
  var res = UrlFetchApp.fetch(ODOO_URL + "/jsonrpc", options);
  var json = JSON.parse(res.getContentText());
  return !json.error;
}

// ==========================================
// FUNGSI UTAMA SINKRONISASI ODOMETER
// ==========================================
function sinkronisasiOdometerCartrack() {
  Logger.log("🚀 Memulai sinkronisasi...");
  
  var authHeader = "Basic " + Utilities.base64Encode(CARTRACK_USER + ":" + CARTRACK_PASS);
  var options = {
    "method": "get",
    "headers": {
      "Authorization": authHeader,
      "Accept": "application/json"
    },
    "muteHttpExceptions": true
  };

  try {
    var response = UrlFetchApp.fetch(CARTRACK_BASE_URL, options);
    if (response.getResponseCode() !== 200) {
      Logger.log("❌ Gagal koneksi ke Cartrack.");
      return;
    }

    var resultData = JSON.parse(response.getContentText());
    var vehicles = resultData.data || resultData.vehicles || resultData;

    var odooUid = getOdooUid();
    if (!odooUid) {
      Logger.log("❌ Gagal autentikasi ke Odoo.");
      return;
    }

    var now = new Date();
    var yesterday = new Date(now.getTime() - (24 * 60 * 60 * 1000));
    var targetDateStr = Utilities.formatDate(yesterday, "GMT+7", "yyyy-MM-dd");
    var displayDateStr = Utilities.formatDate(yesterday, "GMT+7", "dd/MM/yy");
    
    var startTimestamp = targetDateStr + " 00:00:00";
    var endTimestamp = targetDateStr + " 23:59:59";

    var batchId = "BATCH-" + Utilities.formatDate(now, "GMT+7", "yyyyMMdd-HHmmss");
    var executionTimestamp = Utilities.formatDate(now, "GMT+7", "yyyy-MM-dd HH:mm:ss");

    var rowsToAppend = [];

    for (var i = 0; i < vehicles.length; i++) {
      var v = vehicles[i];
      var reg = v.registration || v.reg || v.plate || v.name; 
      
      if (!reg) continue;

      var odoUrl = CARTRACK_BASE_URL + "/" + encodeURIComponent(reg) + "/odometer?start_timestamp=" + encodeURIComponent(startTimestamp) + "&end_timestamp=" + encodeURIComponent(endTimestamp);
      var odoRes = UrlFetchApp.fetch(odoUrl, options);
      
      var val = 0;
      var statusStr = "Gagal";

      if (odoRes.getResponseCode() === 200) {
        var odoData = JSON.parse(odoRes.getContentText());
        
        var rawVal = 0;
        var records = null;
        if (Array.isArray(odoData)) {
          records = odoData;
        } else if (odoData.data) {
          if (Array.isArray(odoData.data)) {
            records = odoData.data;
          } else if (typeof odoData.data === 'object' && odoData.data !== null) {
            rawVal = odoData.data.current_odometer_value !== undefined ? Number(odoData.data.current_odometer_value) :
                     odoData.data.odometer !== undefined ? Number(odoData.data.odometer) : 
                     odoData.data.value !== undefined ? Number(odoData.data.value) : 0;
          }
        }
        
        if (records && records.length > 0) {
          var lastRecord = records[records.length - 1];
          rawVal = lastRecord.current_odometer_value !== undefined ? Number(lastRecord.current_odometer_value) :
                   lastRecord.odometer !== undefined ? Number(lastRecord.odometer) :
                   lastRecord.value !== undefined ? Number(lastRecord.value) :
                   lastRecord.distance !== undefined ? Number(lastRecord.distance) : 0;
        } else if (odoData.odometer !== undefined) {
          rawVal = Number(odoData.odometer);
        } else if (odoData.value !== undefined) {
          rawVal = Number(odoData.value);
        }

        // Konversi Cerdas: Jika nilainya besar (> 200.000), diasumsikan Meter dan dibagi 1000. Jika kecil, biarkan.
        if (rawVal > 200000) {
          val = Math.round(rawVal / 1000);
        } else {
          val = rawVal;
        }

        var odooVehicleId = odooSearch(odooUid, "fleet.vehicle", [["name", "ilike", reg]]);
        if (odooVehicleId) {
          if (val > 0) {
            var sukses = kirimOdometerKeOdoo(odooUid, odooVehicleId, val, targetDateStr);
            if (sukses) {
              statusStr = "Sukses";
            } else {
              statusStr = "Gagal (Odoo Error)";
            }
          } else {
            statusStr = "Gagal (Odometer 0 / Kosong)";
          }
        } else {
          statusStr = "Gagal (Tidak ada di Odoo)";
        }
      }

      rowsToAppend.push([displayDateStr, reg, val, statusStr, batchId, executionTimestamp]);
    }

    var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Fleet Odometer");
    if (!sheet) {
      sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    }

    if (sheet.getLastRow() === 0) {
      sheet.appendRow(["Tanggal", "Vehicle No", "Odometer Value", "Status", "Batch Id", "Timestamp"]);
    }

    if (rowsToAppend.length > 0) {
      sheet.getRange(sheet.getLastRow() + 1, 1, rowsToAppend.length, rowsToAppend[0].length).setValues(rowsToAppend);
      Logger.log("🎉 Selesai! Batch ID: " + batchId);
    }

  } catch (e) {
    Logger.log("❌ Error: " + e.toString());
  }
}

// ==========================================
// FUNGSI UJI COBA MANUAL `kirimOdometerKeOdoo`
// ==========================================
function testKirimOdometerManual() {
  var uid = getOdooUid();
  if (!uid) {
    Logger.log("❌ Gagal autentikasi ke Odoo!");
    return;
  }

  var targetPlat = "R8636OD"; 
  var odooVehicleId = odooSearch(uid, "fleet.vehicle", [["name", "ilike", targetPlat]]);

  if (!odooVehicleId) {
    Logger.log("⚠️ Kendaraan dengan plat nomor " + targetPlat + " tidak ditemukan di Odoo.");
    return;
  }

  var nilaiOdometer = 30327; 
  var tanggalData = "2026-07-30"; 

  var sukses = kirimOdometerKeOdoo(uid, odooVehicleId, nilaiOdometer, tanggalData);

  if (sukses) {
    Logger.log("✅ Berhasil! Data odometer " + targetPlat + " sukses dikirim manual ke Odoo.");
  } else {
    Logger.log("❌ Gagal mengirim data ke Odoo.");
  }
}

// ==========================================
// PENGATUR JADWAL OTOMATIS (TRIGGER)
// ==========================================
function buatJadwalTengahMalam() {
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() == "sinkronisasiOdometerCartrack") {
      ScriptApp.deleteTrigger(triggers[i]);
    }
  }
  ScriptApp.newTrigger("sinkronisasiOdometerCartrack")
    .timeBased()
    .everyDays(1)
    .atHour(0)
    .create();
    
  Logger.log("Jadwal otomatis tengah malam berhasil diaktifkan!");
}

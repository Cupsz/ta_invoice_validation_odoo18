/** @odoo-module **/

import { Component, onWillStart, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class InvoiceValidationDashboard extends Component {
    static template = "invoice_validation.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.fileInputRef = useRef("fileInput");

        this.state = useState({
            // 'dashboard' | 'upload' | 'detail' | 'result'
            view: "dashboard",
            loading: true,

            // dashboard data
            match_count: 0,
            mismatch_count: 0,
            waiting_count: 0,
            recent: [],

            // upload step
            uploading: false,
            isDragging: false,
            fileName: "",
            fileBase64: "",

            // ocr / validate step
            processing: false,
            detail: null,
            rawTextOpen: false,
        });

        onWillStart(async () => {
            await this.loadDashboard();
        });
    }

    /* ---------------------------------------------------------- */
    /* Dashboard                                                   */
    /* ---------------------------------------------------------- */
    async loadDashboard() {
        this.state.loading = true;
        const data = await this.orm.call("invoice.validation", "get_dashboard_data", []);
        this.state.match_count = data.match_count;
        this.state.mismatch_count = data.mismatch_count;
        this.state.waiting_count = data.waiting_count;
        this.state.recent = data.recent;
        this.state.loading = false;
    }

    goToDashboard() {
        this.state.view = "dashboard";
        this.state.fileName = "";
        this.state.fileBase64 = "";
        this.state.detail = null;
        this.state.rawTextOpen = false;
        this.loadDashboard();
    }

    async openRecord(id) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "invoice.validation",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async openFiltered(stateFilter) {
        const domain = stateFilter ? [["state", "=", stateFilter]] : [];
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Invoice Validation",
            res_model: "invoice.validation",
            views: [[false, "list"], [false, "form"]],
            domain: domain,
            target: "current",
        });
    }

    statusBadgeClass(state) {
        if (state === "validated") return "ivdash-badge ivdash-badge-VALID";
        if (state === "INVALID") return "ivdash-badge ivdash-badge-INVALID";
        if (state === "draft") return "ivdash-badge ivdash-badge-waiting";
        if (state === "duplicate") return "ivdash-badge ivdash-badge-duplicate";
        if (state === "incomplete") return "ivdash-badge ivdash-badge-incomplete";
        return "ivdash-badge";
    }

    toggleRawText() {
        this.state.rawTextOpen = !this.state.rawTextOpen;
    }

    /* ---------------------------------------------------------- */
    /* Step 2 — Upload                                              */
    /* ---------------------------------------------------------- */
    openUpload() {
        this.state.view = "upload";
        this.state.fileName = "";
        this.state.fileBase64 = "";
    }

    triggerFilePicker() {
        if (this.fileInputRef.el) {
            this.fileInputRef.el.click();
        }
    }

    onFileChange(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (file) {
            this._readFile(file);
        }
    }

    onDragOver(ev) {
        ev.preventDefault();
        this.state.isDragging = true;
    }

    onDragLeave(ev) {
        ev.preventDefault();
        this.state.isDragging = false;
    }

    onDrop(ev) {
        ev.preventDefault();
        this.state.isDragging = false;
        const file = ev.dataTransfer.files && ev.dataTransfer.files[0];
        if (file) {
            this._readFile(file);
        }
    }

    _readFile(file) {
        if (file.type !== "application/pdf") {
            this.notification.add("Hanya file PDF yang didukung.", { type: "danger" });
            return;
        }
        const reader = new FileReader();
        reader.onload = () => {
            this.state.fileBase64 = reader.result.split(",")[1];
            this.state.fileName = file.name;
        };
        reader.onerror = () => {
            this.notification.add("Gagal membaca file.", { type: "danger" });
        };
        reader.readAsDataURL(file);
    }

    clearFile() {
        this.state.fileName = "";
        this.state.fileBase64 = "";
        if (this.fileInputRef.el) {
            this.fileInputRef.el.value = "";
        }
    }

    cancelUpload() {
        this.goToDashboard();
    }

    /* ---------------------------------------------------------- */
    /* Step 3 — OCR & Parsing                                       */
    /* ---------------------------------------------------------- */
    async submitUpload() {
        if (!this.state.fileBase64) {
            this.notification.add("Silakan pilih file Invoice PDF terlebih dahulu.", { type: "warning" });
            return;
        }
        this.state.uploading = true;
        try {
            const newId = await this.orm.create("invoice.validation", [{
                invoice_file: this.state.fileBase64,
                invoice_filename: this.state.fileName,
            }]);
            const recId = Array.isArray(newId) ? newId[0] : newId;

            this.state.processing = true;
            await this.orm.call("invoice.validation", "action_run_ocr", [[recId]]);
            const detail = await this.orm.call("invoice.validation", "get_validation_detail", [recId]);

            this.state.detail = detail;
            this.state.view = "detail";
            this.notification.add("OCR selesai. Silakan periksa data dan klik Validate.", { type: "success" });
        } catch (error) {
            const msg = (error && error.data && error.data.message) || "Terjadi kesalahan saat memproses invoice.";
            this.notification.add(msg, { type: "danger" });
        } finally {
            this.state.uploading = false;
            this.state.processing = false;
        }
    }

    /* ---------------------------------------------------------- */
    /* Step 4 — Three-Way Matching                                  */
    /* ---------------------------------------------------------- */
    async runValidate() {
        if (!this.state.detail) return;
        if (!this.state.detail.can_validate) {
            this.notification.add("Invoice ini belum bisa divalidasi. Selesaikan pengecekan awal terlebih dahulu.", { type: "warning" });
            return;
        }
        this.state.processing = true;
        try {
            await this.orm.call("invoice.validation", "action_validate", [[this.state.detail.id]]);
            const detail = await this.orm.call("invoice.validation", "get_validation_detail", [this.state.detail.id]);
            this.state.detail = detail;
            this.state.view = "result";
        } catch (error) {
            const msg = (error && error.data && error.data.message) || "Gagal menjalankan validasi.";
            this.notification.add(msg, { type: "danger" });
        } finally {
            this.state.processing = false;
        }
    }

    backToDetail() {
        this.state.view = "detail";
    }

    async viewFullRecord() {
        if (this.state.detail) {
            await this.openRecord(this.state.detail.id);
        }
    }

    finishAndReturn() {
        this.goToDashboard();
    }
}

registry.category("actions").add("invoice_validation.dashboard", InvoiceValidationDashboard);

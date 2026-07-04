/** @odoo-module **/

import { registry } from "@web/core/registry";
import { FloatField, floatField } from "@web/views/fields/float/float_field";

/**
 * Parser angka Rupiah gaya Indonesia, TIDAK bergantung pada setting
 * Language user yang sedang aktif:
 *   - "."  dianggap pemisah RIBUAN   -> "10.000"      = 10000
 *   - ","  dianggap pemisah DESIMAL  -> "10.000,50"   = 10000.5
 *   - Angka polos tetap didukung     -> "10000"       = 10000
 *
 * Heuristik saat HANYA ada titik (tanpa koma): kalau kelompok digit
 * terakhir setelah titik persis 3 angka, titik itu ribuan
 * (mis. "1.000.000" -> 1000000). Kalau kelompok terakhirnya 1-2
 * angka, titik itu dianggap desimal (mis. "10.5" -> 10.5).
 * Logika ini sengaja disamakan dengan parser angka di OCR service
 * (_parse_number di ocr_service.py) supaya konsisten satu aplikasi.
 */
function parseIdrAmount(value) {
    if (value === "" || value === undefined || value === null) {
        return 0;
    }
    let str = String(value).trim().replace(/(rp\.?|idr)/gi, "").trim();
    str = str.replace(/[^0-9.,\-]/g, "");
    if (!str) {
        return 0;
    }

    const hasComma = str.includes(",");
    const hasDot = str.includes(".");

    if (hasComma && hasDot) {
        str = str.replace(/\./g, "").replace(",", ".");
    } else if (hasComma && !hasDot) {
        str = str.replace(",", ".");
    } else if (hasDot && !hasComma) {
        const parts = str.split(".");
        const lastGroup = parts[parts.length - 1];
        if (lastGroup.length !== 3) {
            // kelompok terakhir bukan 3 digit -> ini desimal, bukan ribuan
            // (biarkan titik tetap ada, akan diparse sebagai desimal)
        } else {
            str = str.replace(/\./g, "");
        }
    }

    const num = parseFloat(str);
    return isNaN(num) ? 0 : num;
}

/**
 * Field harga (Rupiah) yang selalu tampil & terbaca dengan format
 * Indonesia, dipakai untuk Unit Price / Subtotal / Total di Purchase
 * Order supaya tidak ada lagi kejadian angka yang diketik user
 * "hilang"/salah baca gara-gara titik dikira desimal.
 */
export class PriceIdrField extends FloatField {
    get formattedValue() {
        const value = this.props.record.data[this.props.name];
        if (value === false || value === undefined || value === null) {
            return "Rp 0";
        }
        const formatted = new Intl.NumberFormat("id-ID", {
            minimumFractionDigits: 0,
            maximumFractionDigits: 2,
        }).format(value);
        return `Rp ${formatted}`;
    }

    parse(value) {
        return parseIdrAmount(value);
    }
}

export const priceIdrField = {
    ...floatField,
    component: PriceIdrField,
};

registry.category("fields").add("price_idr", priceIdrField);

/**
 * Varian "singkatan ribuan" khusus untuk Unit Price: user cukup ketik
 * angka pendek, otomatis dikalikan 1000 sebagai harga sebenarnya.
 *   ketik "10"  -> tersimpan & dipakai sebagai Rp 10.000
 *   ketik "1,5" -> tersimpan & dipakai sebagai Rp 1.500
 *   ketik "1"   -> tersimpan & dipakai sebagai Rp 1.000
 *
 * Nilai ASLI (sudah dikali 1000) itulah yang disimpan ke field
 * price_unit -> supaya Subtotal & Total (dihitung Odoo di backend)
 * otomatis benar. Untuk tampilan, nilai asli itu dibagi 1000 lagi
 * supaya yang kelihatan di kolom Unit Price tetap angka pendek yang
 * konsisten dengan yang diketik (baik saat idle maupun saat diedit).
 */
export class PriceIdrRibuanField extends PriceIdrField {
    get formattedValue() {
        const value = this.props.record.data[this.props.name];
        if (value === false || value === undefined || value === null || value === 0) {
            return "0";
        }
        const shorthand = value / 1000;
        return new Intl.NumberFormat("id-ID", {
            minimumFractionDigits: 0,
            maximumFractionDigits: 2,
        }).format(shorthand);
    }

    parse(value) {
        return parseIdrAmount(value) * 1000;
    }
}

export const priceIdrRibuanField = {
    ...floatField,
    component: PriceIdrRibuanField,
};

registry.category("fields").add("price_idr_ribuan", priceIdrRibuanField);

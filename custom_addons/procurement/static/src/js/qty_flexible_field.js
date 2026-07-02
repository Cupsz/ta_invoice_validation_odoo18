/** @odoo-module **/

import { registry } from "@web/core/registry";
import { FloatField, floatField } from "@web/views/fields/float/float_field";

/**
 * Field Quantity yang fleksibel: tidak memaksa tampil "10.00" untuk
 * angka bulat. Nilai tetap disimpan sebagai float biasa (mendukung
 * desimal untuk barang timbang seperti kg), tapi ditampilkan tanpa
 * angka nol yang tidak perlu di belakang koma.
 *   10      -> "10"      (misal: 10 karung beras)
 *   10.5    -> "10,5"    (misal: 10,5 kg ikan)
 *   10.25   -> "10,25"
 * Pengetikan/edit tetap seperti field angka biasa.
 */
export class QtyFlexibleField extends FloatField {
    get formattedValue() {
        const value = this.props.record.data[this.props.name];
        if (value === false || value === undefined || value === null) {
            return "";
        }
        return new Intl.NumberFormat("id-ID", {
            minimumFractionDigits: 0,
            maximumFractionDigits: 2,
        }).format(value);
    }
}

export const qtyFlexibleField = {
    ...floatField,
    component: QtyFlexibleField,
};

registry.category("fields").add("qty_flexible", qtyFlexibleField);

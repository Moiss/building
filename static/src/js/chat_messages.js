/** @odoo-module **/
// Componente OWL para renderizar mensajes del chat IA en formato WhatsApp.
// Sustituye al <kanban> nativo que no soporta layout vertical real.

import { Component, onMounted, onPatched, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class BuildingChatMessages extends Component {
    static template = "building_dashboard.ChatMessages";
    static props = { ...standardFieldProps };

    setup() {
        this.messagesEndRef = useRef("messagesEnd");
        onMounted(() => this._scrollToBottom());
        onPatched(() => this._scrollToBottom());
    }

    _scrollToBottom() {
        const el = this.messagesEndRef.el;
        if (el) {
            el.scrollIntoView({ behavior: "smooth", block: "end" });
        }
    }

    get list() {
        return this.props.record.data[this.props.name];
    }

    get mensajes() {
        return this.list ? this.list.records : [];
    }
}

registry.category("fields").add("building_chat_messages", {
    component: BuildingChatMessages,
    supportedTypes: ["one2many"],
    relatedFields: [
        { name: "role", type: "selection" },
        { name: "content", type: "text" },
    ],
});

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Hyprland
import qs.Commons

PopupWindow {
    id: popup
    required property Item anchorItem
    required property QtObject bar
    required property var owner
    property bool open: false
    property bool busy: false
    property string companyName: ""
    property string projectName: ""
    property bool managingRecords: false
    property string deletionCommand: ""
    property int deletionId: 0
    property string deletionLabel: ""
    function setVault(path) { vaultPath.text = path }
    function showReport(format) {
        var args = ["report", period.currentText.toLowerCase()]
        if (reportDate.text.trim()) args.push("--date", reportDate.text.trim())
        if (scope.currentIndex > 0) args.push("--company", popup.companyName)
        if (scope.currentIndex === 2) args.push("--project", popup.projectName)
        if (format === "pdf") args.push("--pdf")
        if (format === "obsidian") args.push("--obsidian")
        owner.request(args)
    }
    readonly property var anchorWindow: anchorItem ? anchorItem.QsWindow.window : null
    readonly property color fg: Color.popups.text
    readonly property color bg: Color.popups.background
    readonly property var projectNames: {
        var company = owner.companies.find(function(c) { return c.name === popup.companyName })
        return ["General company time"].concat(owner.projects.filter(function(p) {
            return company && p.company_id === company.id
        }).map(function(p) { return p.name }))
    }
    implicitWidth: 460
    implicitHeight: Math.min(720, content.implicitHeight + 28)
    visible: open
    color: "transparent"
    onOpenChanged: {
        deletionCommand = ""
        deleteConfirmation.clear()
        if (open) {
            bar.requestPopout(owner)
            companyName = owner.trackerState.selected_company || (owner.companies.length ? owner.companies[0].name : "")
            projectName = owner.trackerState.selected_project || ""
            vaultPath.text = owner.trackerState.obsidian_vault || ""
        } else if (bar.activePopout === owner) bar.releasePopout(owner)
    }
    HyprlandFocusGrab {
        active: popup.open
        windows: popup.anchorWindow ? [popup, popup.anchorWindow] : [popup]
        onCleared: popup.open = false
    }
    anchor {
        id: placement
        window: popup.anchorWindow
        adjustment: PopupAdjustment.Slide
        edges: Edges.Top | Edges.Left
        gravity: Edges.Bottom | Edges.Right
        rect.width: 1
        rect.height: 1
        onAnchoring: {
            if (!popup.anchorWindow) return
            var x = anchorItem.width / 2 - popup.width / 2
            var y = anchorItem.height + 10
            if (bar.position === "bottom") y = -popup.height - 10
            if (bar.position === "left") { x = anchorItem.width + 10; y = 0 }
            if (bar.position === "right") { x = -popup.width - 10; y = 0 }
            var p = popup.anchorWindow.contentItem.mapFromItem(anchorItem, x, y)
            placement.rect.x = Math.max(10, Math.min(p.x, popup.anchorWindow.width - popup.width - 10))
            placement.rect.y = p.y
        }
    }
    Rectangle {
        anchors.fill: parent
        color: popup.bg
        border.color: Color.popups.border
        border.width: 2
        ScrollView {
            anchors.fill: parent
            anchors.margins: 14
            clip: true
            contentWidth: availableWidth
            ColumnLayout {
                id: content
                width: parent.width
                spacing: 9
                RowLayout {
                    Layout.fillWidth: true
                    Label { text: "Time Tracker"; color: popup.fg; font.pixelSize: 19; font.bold: true; Layout.fillWidth: true }
                    Button { text: "Close"; onClicked: popup.open = false }
                }
                Label {
                    text: owner.trackerState.running ? owner.duration(owner.elapsed) : "Ready to track"
                    color: popup.fg; font.pixelSize: 28; font.bold: true
                }
                Label {
                    Layout.fillWidth: true; wrapMode: Text.WordWrap; textFormat: Text.PlainText; color: popup.fg
                    text: owner.trackerState.running ? owner.trackerState.running.company + " · " + (owner.trackerState.running.project || "General company time") : "Choose a company and optional project below."
                }
                Label { text: "Company"; color: popup.fg }
                NameBox {
                    Layout.fillWidth: true
                    model: owner.companies.map(function(c) { return c.name })
                    currentIndex: model.indexOf(popup.companyName)
                    onActivated: { popup.companyName = currentText; popup.projectName = "" }
                }
                RowLayout {
                    Layout.fillWidth: true
                    TextField { id: newCompany; placeholderText: "New company name"; maximumLength: 200; Layout.fillWidth: true }
                    Button {
                        text: "Add"
                        enabled: !popup.busy && newCompany.text.trim().length > 0
                        onClicked: {
                            popup.companyName = newCompany.text.trim(); popup.projectName = ""
                            owner.request(["add-company", popup.companyName]); newCompany.clear()
                        }
                    }
                }
                Label { text: "Project"; color: popup.fg }
                NameBox {
                    Layout.fillWidth: true; model: popup.projectNames
                    currentIndex: Math.max(0, model.indexOf(popup.projectName))
                    onActivated: popup.projectName = currentIndex === 0 ? "" : currentText
                }
                RowLayout {
                    Layout.fillWidth: true
                    TextField { id: newProject; placeholderText: "New project name"; maximumLength: 200; Layout.fillWidth: true }
                    Button {
                        text: "Add"
                        enabled: !popup.busy && popup.companyName !== "" && newProject.text.trim().length > 0
                        onClicked: {
                            popup.projectName = newProject.text.trim()
                            owner.request(["add-project", popup.projectName, "--company", popup.companyName]); newProject.clear()
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    Button {
                        text: owner.trackerState.running ? "Stop timer" : "Start timer"
                        Layout.fillWidth: true
                        enabled: !popup.busy && (owner.trackerState.running !== null || popup.companyName !== "")
                        onClicked: {
                            var args = owner.trackerState.running ? ["stop"] : ["start", "--company", popup.companyName]
                            if (!owner.trackerState.running && popup.projectName) args.push("--project", popup.projectName)
                            owner.request(args)
                        }
                    }
                    Button {
                        text: "Save selection"
                        enabled: !popup.busy && popup.companyName !== ""
                        onClicked: {
                            var args = ["select", "--company", popup.companyName]
                            if (popup.projectName) args.push("--project", popup.projectName)
                            owner.request(args)
                        }
                    }
                }
                Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Color.popups.border }
                Label { text: "Reports"; color: popup.fg; font.pixelSize: 16; font.bold: true }
                RowLayout {
                    Layout.fillWidth: true
                    ComboBox { id: period; model: ["Daily", "Weekly", "Monthly", "Yearly"]; Layout.preferredWidth: 125 }
                    TextField { id: reportDate; placeholderText: "Date (optional): YYYY-MM-DD"; Layout.fillWidth: true }
                }
                RowLayout {
                    Layout.fillWidth: true
                    ComboBox { id: scope; model: ["All companies", "Selected company", "Selected project"]; Layout.fillWidth: true }

                }
                RowLayout {
                    Layout.fillWidth: true
                    Button {
                        text: "Export PDF"
                        Layout.fillWidth: true
                        enabled: !popup.busy && (scope.currentIndex === 0 || popup.companyName !== "") && (scope.currentIndex !== 2 || popup.projectName !== "")
                        onClicked: popup.showReport("pdf")
                    }
                    Button {
                        text: "Open PDF"
                        visible: owner.pdfPath !== ""
                        onClicked: { Quickshell.execDetached(["/usr/bin/xdg-open", owner.pdfPath]); popup.open = false }
                    }
                }
                Label {
                    visible: owner.pdfPath !== ""
                    text: "Saved: " + owner.pdfPath
                    color: popup.fg; textFormat: Text.PlainText; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true
                    font.pixelSize: 11
                }
                Label { text: "Obsidian vault"; color: popup.fg; font.bold: true }
                Switch {
                    text: "Log each stopped timer to Obsidian"
                    checked: owner.trackerState.obsidian_autolog === true
                    enabled: !popup.busy && !!owner.trackerState.obsidian_vault
                    onClicked: owner.request(["auto-obsidian", checked ? "on" : "off"])
                }
                RowLayout {
                    visible: (owner.trackerState.obsidian_pending || 0) > 0
                    Layout.fillWidth: true
                    Label { text: (owner.trackerState.obsidian_pending || 0) + " session(s) waiting to log"; color: popup.fg; Layout.fillWidth: true }
                    Button { text: "Retry logging"; enabled: !popup.busy; onClicked: owner.request(["retry-obsidian"]) }
                }
                RowLayout {
                    Layout.fillWidth: true
                    TextField { id: vaultPath; placeholderText: "Full path to your vault folder"; maximumLength: 4096; Layout.fillWidth: true }
                    Button {
                        text: "Save vault"
                        enabled: !popup.busy && vaultPath.text.trim() !== ""
                        onClicked: owner.request(["vault", vaultPath.text.trim()])
                    }
                    Button {
                        text: "Clear"
                        enabled: !popup.busy && !!owner.trackerState.obsidian_vault
                        onClicked: { owner.request(["vault", "--clear"]); vaultPath.clear() }
                    }
                }
                Button {
                    text: "View Obsidian"
                    Layout.fillWidth: true
                    enabled: !!owner.trackerState.obsidian_vault
                    onClicked: {
                        var uri = owner.obsidianUri || "obsidian://open?path=" + encodeURIComponent(owner.trackerState.obsidian_vault)
                        Quickshell.execDetached(["/usr/bin/xdg-open", uri])
                        popup.open = false
                    }
                }
                Label {
                    visible: owner.errorText !== ""
                    text: owner.errorText; color: Color.urgent; wrapMode: Text.WordWrap; textFormat: Text.PlainText; Layout.fillWidth: true
                }
                Button {
                    text: popup.managingRecords ? "Hide record management" : "Manage records"
                    Layout.fillWidth: true
                    enabled: !popup.busy
                    onClicked: {
                        popup.managingRecords = !popup.managingRecords
                        popup.deletionCommand = ""
                        owner.recordMessage = ""
                        if (popup.managingRecords) owner.request(["records", "--limit", "10000"])
                    }
                }
                ColumnLayout {
                    visible: popup.managingRecords
                    Layout.fillWidth: true
                    Label {
                        text: "Delete database records. Companies, projects, settings, exported PDFs and Obsidian notes stay. Pending Obsidian logs for deleted records are cancelled."
                        color: popup.fg; wrapMode: Text.WordWrap; Layout.fillWidth: true
                    }
                    NameBox {
                        id: recordPicker
                        Layout.fillWidth: true
                        model: owner.records.filter(function(r) { return r.end !== null }).map(function(r) {
                            return "#" + r.id + " · " + r.start.slice(0, 16).replace("T", " ") + " · " + r.company + " · " + (r.project || "General company time") + " · " + owner.duration(r.seconds)
                        })
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Button {
                            text: "Delete selected"
                            enabled: !popup.busy && recordPicker.currentIndex >= 0
                            onClicked: {
                                var record = owner.records.filter(function(r) { return r.end !== null })[recordPicker.currentIndex]
                                if (!record) return
                                popup.deletionId = record.id
                                popup.deletionLabel = recordPicker.currentText
                                popup.deletionCommand = "delete-record"
                                deleteConfirmation.clear()
                            }
                        }
                        Button {
                            text: "Clear all records"
                            enabled: !popup.busy && !owner.trackerState.running && owner.records.length > 0
                            onClicked: { popup.deletionCommand = "clear-records"; deleteConfirmation.clear() }
                        }
                        Button { text: "Refresh"; enabled: !popup.busy; onClicked: { popup.deletionCommand = ""; owner.request(["records", "--limit", "10000"]) } }
                    }
                    Label {
                        visible: !!owner.trackerState.running
                        text: "Stop the timer before clearing all records."
                        color: popup.fg
                    }
                    ColumnLayout {
                        visible: popup.deletionCommand !== ""
                        Layout.fillWidth: true
                        Label {
                            text: (popup.deletionCommand === "clear-records" ? "Permanently delete ALL time records for every company?" : "Permanently delete " + popup.deletionLabel + "?") + " Type DELETE to confirm."
                            color: popup.fg; wrapMode: Text.WordWrap; textFormat: Text.PlainText; Layout.fillWidth: true
                        }
                        RowLayout {
                            TextField { id: deleteConfirmation; placeholderText: "DELETE"; Layout.fillWidth: true }
                            Button {
                                text: "Confirm deletion"
                                enabled: !popup.busy && deleteConfirmation.text === "DELETE"
                                onClicked: {
                                    var args = [popup.deletionCommand]
                                    if (popup.deletionCommand === "delete-record") args.push(String(popup.deletionId))
                                    args.push("--confirm")
                                    owner.request(args)
                                    popup.deletionCommand = ""
                                    deleteConfirmation.clear()
                                }
                            }
                            Button { text: "Cancel"; onClicked: { popup.deletionCommand = ""; deleteConfirmation.clear() } }
                        }
                    }
                    Label { text: owner.recordMessage; visible: text !== ""; color: popup.fg }
                }
                Label { text: "Timezone: " + (owner.trackerState.timezone || "Loading…"); color: popup.fg; opacity: 0.65; font.pixelSize: 11 }
            }
        }
    }
    component NameBox: ComboBox {
        id: box
        contentItem: Text {
            text: box.displayText
            textFormat: Text.PlainText
            color: box.palette.buttonText
            font: box.font
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        delegate: ItemDelegate {
            id: option
            required property var modelData
            required property int index
            width: box.width
            highlighted: box.highlightedIndex === index
            contentItem: Text {
                text: String(option.modelData)
                textFormat: Text.PlainText
                color: option.palette.text
                font: box.font
                elide: Text.ElideRight
            }
        }
    }
}

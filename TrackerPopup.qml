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
    function showReport(exportPdf) {
        var args = ["report", period.currentText.toLowerCase()]
        if (reportDate.text.trim()) args.push("--date", reportDate.text.trim())
        if (scope.currentIndex > 0) args.push("--company", popup.companyName)
        if (scope.currentIndex === 2) args.push("--project", popup.projectName)
        if (exportPdf) args.push("--pdf")
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
        if (open) {
            bar.requestPopout(owner)
            companyName = owner.trackerState.selected_company || (owner.companies.length ? owner.companies[0].name : "")
            projectName = owner.trackerState.selected_project || ""
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
                    Button {
                        text: "Show report"
                        enabled: !popup.busy && (scope.currentIndex === 0 || popup.companyName !== "") && (scope.currentIndex !== 2 || popup.projectName !== "")
                        onClicked: popup.showReport(false)
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    Button {
                        text: "Export PDF"
                        Layout.fillWidth: true
                        enabled: !popup.busy && (scope.currentIndex === 0 || popup.companyName !== "") && (scope.currentIndex !== 2 || popup.projectName !== "")
                        onClicked: popup.showReport(true)
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
                Label {
                    Layout.fillWidth: true; wrapMode: Text.WordWrap; textFormat: Text.PlainText; color: popup.fg
                    text: {
                        var r = owner.reportData
                        if (!r) return "Weeks start Monday. Leave date blank for the current period."
                        var lines = [r.start + " → " + r.end_exclusive + " (end excluded)",
                                     "Total: " + owner.duration(r.total_seconds) + (r.includes_running_timer ? " · timer running" : "")]
                        r.companies.forEach(function(c) { lines.push(c.company + ": " + owner.duration(c.seconds)) })
                        r.projects.forEach(function(p) { lines.push("  " + p.company + " / " + (p.project || "General") + ": " + owner.duration(p.seconds)) })
                        r.daily.forEach(function(d) { lines.push(d.date + " · " + d.company + " / " + (d.project || "General") + ": " + owner.duration(d.seconds)) })
                        return lines.join("\n")
                    }
                }
                Label {
                    visible: owner.errorText !== ""
                    text: owner.errorText; color: Color.urgent; wrapMode: Text.WordWrap; textFormat: Text.PlainText; Layout.fillWidth: true
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

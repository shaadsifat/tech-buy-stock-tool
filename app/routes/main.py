from datetime import datetime

from flask import Blueprint, render_template, jsonify, send_file, redirect, url_for, flash

from app import models
from app.scraping import runner
from app.export.excel_export import build_workbook, build_filename

main_bp = Blueprint("main", __name__)


def _build_summary_text(s):
    pct = round((s["remaining"] / s["flagged_total"] * 100), 1) if s["flagged_total"] else 0
    now = datetime.now()
    date_str = f"{now.day} {now.strftime('%B')}, {now.year}"
    lines = [
        f"Date: {date_str}",
        f"Total Listed Products: {s['total']}",
        f"Stock-out Found: {s['stockout']}",
        f"Total Already Updated Price Found: {s['already_updated']}",
        f"Total Price Updated Today: {s['updated_today']}",
        f"Update Remaining: {s['remaining']}",
        "",
        f"{s['remaining']} of {s['flagged_total']} products ({pct}%) still need price review.",
    ]
    return "\n".join(lines)


@main_bp.route("/", methods=["GET"])
def index():
    fetched_count = models.count_fetch_results()
    data = models.get_dashboard_data()
    return render_template(
        "main.html",
        fetched_count=fetched_count,
        stats=data["stats"],
        report=data["report"],
        summary_text=_build_summary_text(data["summary"]),
    )


@main_bp.route("/fetch/start", methods=["POST"])
def fetch_start():
    started = runner.start_fetch()
    if not started:
        return jsonify({"ok": False, "error": "A fetch is already running."}), 409
    return jsonify({"ok": True})


@main_bp.route("/fetch/status", methods=["GET"])
def fetch_status():
    return jsonify(runner.get_status())


@main_bp.route("/fetch/stop", methods=["POST"])
def fetch_stop():
    stopped = runner.stop_fetch()
    if not stopped:
        return jsonify({"ok": False, "error": "No fetch is currently running."}), 409
    return jsonify({"ok": True})


@main_bp.route("/dashboard/stats", methods=["GET"])
def dashboard_stats():
    data = models.get_dashboard_data()
    return jsonify({
        "ok": True,
        "fetched_count": models.count_fetch_results(),
        "stats": data["stats"],
        "report": data["report"],
        "summary_text": _build_summary_text(data["summary"]),
    })


@main_bp.route("/fetch/clear", methods=["POST"])
def fetch_clear():
    models.clear_fetch_results()
    flash("Previously fetched data removed.", "success")
    return redirect(url_for("main.index"))


@main_bp.route("/export/excel", methods=["GET"])
def export_excel():
    buffer = build_workbook()
    return send_file(
        buffer,
        as_attachment=True,
        download_name=build_filename(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@main_bp.route("/guide", methods=["GET"])
def guide():
    return render_template("guide.html")

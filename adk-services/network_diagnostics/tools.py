import sqlite3


DB_PATH = r"D:\Prodapt_Phase_2\data\telecom_ops.db"


def check_tower_status(tower_id: str) -> dict:

    connection = sqlite3.connect(DB_PATH)

    # Get tower information
    tower_query = """
    SELECT
        tower_id,
        tower_name,
        region,
        city,
        state,
        technology,
        status
    FROM network_towers
    WHERE tower_id = ?
    """

    tower = connection.execute(
        tower_query,
        (tower_id,)
    ).fetchone()

    if tower is None:
        connection.close()

        return {
            "success": False,
            "message": f"Tower {tower_id} was not found."
        }

    # Get latest performance
    performance_query = """
    SELECT
        recorded_at,
        latency_ms,
        packet_loss_pct,
        downlink_throughput_mbps,
        uplink_throughput_mbps,
        signal_strength_dbm,
        active_connections
    FROM tower_performance
    WHERE tower_id = ?
    ORDER BY recorded_at DESC
    LIMIT 1
    """

    performance = connection.execute(
        performance_query,
        (tower_id,)
    ).fetchone()

    # Get open incident
    incident_query = """
    SELECT
        incident_id,
        severity,
        status,
        title,
        description,
        opened_at,
        classification,
        assigned_team
    FROM open_incidents
    WHERE tower_id = ?
      AND status = 'OPEN'
    ORDER BY opened_at DESC
    LIMIT 1
    """

    incident = connection.execute(
        incident_query,
        (tower_id,)
    ).fetchone()

    connection.close()

    result = {
        "success": True,

        "tower": {
            "tower_id": tower[0],
            "tower_name": tower[1],
            "region": tower[2],
            "city": tower[3],
            "state": tower[4],
            "technology": tower[5],
            "status": tower[6]
        },

        "latest_performance": None,

        "open_incident": None
    }

    if performance:
        result["latest_performance"] = {
            "recorded_at": performance[0],
            "latency_ms": performance[1],
            "packet_loss_pct": performance[2],
            "downlink_throughput_mbps": performance[3],
            "uplink_throughput_mbps": performance[4],
            "signal_strength_dbm": performance[5],
            "active_connections": performance[6]
        }

    if incident:
        result["open_incident"] = {
            "incident_id": incident[0],
            "severity": incident[1],
            "status": incident[2],
            "title": incident[3],
            "description": incident[4],
            "opened_at": incident[5],
            "classification": incident[6],
            "assigned_team": incident[7]
        }

    return result

async def run_connectivity_diagnostics(
    tower_id: str,
    symptom: str
) -> dict:

    connection = sqlite3.connect(DB_PATH)

    query = """
    SELECT
        recorded_at,
        latency_ms,
        packet_loss_pct,
        downlink_throughput_mbps,
        uplink_throughput_mbps,
        signal_strength_dbm,
        active_connections
    FROM tower_performance
    WHERE tower_id = ?
    ORDER BY recorded_at DESC
    LIMIT 1
    """

    performance = connection.execute(
        query,
        (tower_id,)
    ).fetchone()

    connection.close()

    if performance is None:
        return {
            "success": False,
            "message": f"No performance data found for tower {tower_id}."
        }

    (
        recorded_at,
        latency,
        packet_loss,
        downlink,
        uplink,
        signal,
        connections
    ) = performance

    recommendations = []

    symptom_lower = symptom.lower()

    # Slow internet
    if "slow" in symptom_lower or "internet" in symptom_lower:

        if packet_loss > 3:
            recommendations.append(
                "Investigate packet loss because the latest packet loss is above 3%."
            )

        if latency > 50:
            recommendations.append(
                "Investigate network latency because the latest latency is above 50 ms."
            )

        if downlink < 100:
            recommendations.append(
                "Investigate downlink throughput because the latest downlink is below 100 Mbps."
            )

    # Poor signal
    if "signal" in symptom_lower:

        if signal < -80:
            recommendations.append(
                "Investigate radio signal conditions because signal strength is below -80 dBm."
            )

    # Connection drops
    if "drop" in symptom_lower or "disconnect" in symptom_lower:

        if packet_loss > 3:
            recommendations.append(
                "Investigate packet loss because packet loss can contribute to connection instability."
            )

        if signal < -80:
            recommendations.append(
                "Investigate radio signal conditions because signal strength is below -80 dBm."
            )

        if latency > 50:
            recommendations.append(
                "Investigate network latency because the latest latency is above 50 ms."
            )

    if not recommendations:
        recommendations.append(
            "No diagnostic condition was triggered by the configured rules."
        )

    return {
        "success": True,
        "tower_id": tower_id,
        "symptom": symptom,
        "recorded_at": recorded_at,
        "performance": {
            "latency_ms": latency,
            "packet_loss_pct": packet_loss,
            "downlink_throughput_mbps": downlink,
            "uplink_throughput_mbps": uplink,
            "signal_strength_dbm": signal,
            "active_connections": connections
        },
        "recommendations": recommendations
    }

async def get_regional_network_summary(region: str) -> dict:

    connection = sqlite3.connect(DB_PATH)

    query = """
    SELECT
        status,
        COUNT(*) AS tower_count
    FROM network_towers
    WHERE region = ?
    GROUP BY status
    ORDER BY status
    """

    rows = connection.execute(
        query,
        (region,)
    ).fetchall()

    connection.close()

    if not rows:
        return {
            "success": False,
            "message": f"No towers found in region {region}."
        }

    status_counts = {}

    for status, count in rows:
        status_counts[status] = count

    total_towers = sum(status_counts.values())

    operational_count = status_counts.get(
        "OPERATIONAL",
        0
    )

    operational_percentage = (
        operational_count / total_towers
    ) * 100

    return {
        "success": True,
        "region": region,
        "total_towers": total_towers,
        "status_counts": status_counts,
        "operational_percentage": round(
            operational_percentage,
            2
        )
    }
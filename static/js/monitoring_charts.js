document.addEventListener("DOMContentLoaded", function () {
    var chartDataElement = document.getElementById("monitoring-chart-series");

    if (!chartDataElement || typeof Chart === "undefined") {
        return;
    }

    var chartSeries = JSON.parse(chartDataElement.textContent);
    var lineColor = "#2f6feb";
    var criticalColor = "#b42318";
    var gridColor = "#e3e8ef";
    var textColor = "#344054";

    Chart.defaults.font.family = "Arial, sans-serif";
    Chart.defaults.color = textColor;

    document.querySelectorAll(".monitoring-chart").forEach(function (canvas) {
        var chartIndex = Number(canvas.dataset.chartIndex);
        var series = chartSeries[chartIndex];
        var wrap = canvas.closest(".monitoring-chart-wrap");

        if (wrap && wrap.dataset.chartPointCount) {
            wrap.style.setProperty("--chart-point-count", wrap.dataset.chartPointCount);
        }
        if (!series || !series.has_data) {
            return;
        }

        var labels = series.points.map(function (point) {
            return point.date_label;
        });
        var values = series.points.map(function (point) {
            return point.value_float;
        });
        var pointColors = series.points.map(function (point) {
            return point.is_critical ? criticalColor : lineColor;
        });

        new Chart(canvas, {
            type: "line",
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    borderColor: lineColor,
                    backgroundColor: "rgba(47, 111, 235, 0.12)",
                    borderWidth: 2.5,
                    fill: false,
                    showLine: series.has_line,
                    tension: 0.25,
                    pointBackgroundColor: pointColors,
                    pointBorderColor: "#ffffff",
                    pointBorderWidth: 2,
                    pointRadius: 5.5,
                    pointHoverRadius: 8,
                    pointHitRadius: 14
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: {
                    padding: {
                        top: 8,
                        right: 8
                    }
                },
                interaction: {
                    mode: "nearest",
                    intersect: true
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            title: function (items) {
                                return items[0] ? items[0].label : "";
                            },
                            label: function (context) {
                                var point = series.points[context.dataIndex];
                                var value = point ? point.value_display : context.formattedValue;
                                var unit = series.unit ? " " + series.unit : "";
                                return series.label + ": " + value + unit;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: "Дата"
                        },
                        ticks: {
                            autoSkip: true,
                            maxTicksLimit: 8,
                            callback: function (value) {
                                var label = this.getLabelForValue(value);
                                return label ? label.split(" ") : "";
                            }
                        },
                        grid: {
                            color: gridColor
                        },
                        border: {
                            color: gridColor
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: series.unit ? "Значение, " + series.unit : "Значение"
                        },
                        grace: "8%",
                        ticks: {
                            precision: 2
                        },
                        grid: {
                            color: gridColor
                        },
                        border: {
                            color: gridColor
                        }
                    }
                }
            }
        });
    });
});

<script>
new Chart(document.getElementById("barChart"), {
    type: "bar",
    data: {
        labels: ["Resume Skills", "GitHub Skills"],
        datasets: [{
            data: [{{ resume_count }}, {{ github_count }}]
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false
    }
});
</script>

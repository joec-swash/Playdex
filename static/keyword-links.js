document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("form[data-keyword-triggers]").forEach(function (form) {
        let keywords;

        try {
            keywords = JSON.parse(form.dataset.keywordTriggers || "[]");
        } catch (error) {
            console.error("Playdex: Could not read keyword triggers.", error);
            return;
        }

        const titleField = form.querySelector('[name="title"]');
        const reviewField = form.querySelector('[name="review"]');

        // Only check for keywords when the form is submitted.
        form.addEventListener("submit", function () {
            const text = [
                titleField ? titleField.value : "",
                reviewField ? reviewField.value : ""
            ].join("\n").toLowerCase();

            const matchedKeyword = keywords.find(function (keyword) {
                const key = keyword.trim().toLowerCase();
                return key && text.includes(key);
            });

            if (!matchedKeyword) {
                return;
            }

            const key = matchedKeyword.trim().toLowerCase();
            const destination =
                "/keyword-link?keyword=" + encodeURIComponent(key);

            // Open the destination in a new tab when Add/Edit is clicked.
            const tab = window.open(destination, "_blank");

            if (tab) {
                tab.opener = null;
            }
        });
    });
});
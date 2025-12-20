async function loadProfile() {
    try {
        const res = await fetch("/get_profile");
        const data = await res.json();

        document.getElementById("state").innerText = data.state || "-";
        document.getElementById("age").innerText = data.age || "-";
        document.getElementById("gender").innerText = data.gender || "-";
        document.getElementById("occupation").innerText = data.occupation || "-";
        
        // Update eligible schemes section
        updateEligibleSchemes(data.eligible_schemes || []);
    } catch (error) {
        console.error('Error loading profile:', error);
    }
}

function updateEligibleSchemes(schemes) {
    const schemesContainer = document.querySelector('.info-card p');
    if (!schemesContainer) return;
    
    if (!schemes || schemes.length === 0) {
        schemesContainer.innerHTML = 'ఇంకా పథకాలు కనుగొనలేదు';
        return;
    }
    
    // Clean up scheme display - extract only Telugu names, remove all English
    const schemesList = schemes.map(scheme => {
        let teluguName = '';
        
        if (typeof scheme === 'object' && scheme !== null) {
            // Handle object format
            teluguName = scheme.scheme_name_te || scheme.name || '';
        } else if (typeof scheme === 'string') {
            // Handle various string formats
            if (scheme.includes('scheme_name_te')) {
                // Extract from JSON-like string: "{'scheme_name_te': 'రైతు బంధు'}"
                const match = scheme.match(/'scheme_name_te':\s*'([^']+)'/);
                if (match) {
                    teluguName = match[1];
                }
            } else if (scheme.includes(':')) {
                // Handle "scheme_id: name" format, take the name part
                const parts = scheme.split(':');
                if (parts.length > 1) {
                    teluguName = parts[parts.length - 1].trim();
                }
            } else {
                // Direct Telugu text
                teluguName = scheme;
            }
        }
        
        // Clean the Telugu name - remove English characters, symbols, and extra spaces
        if (teluguName) {
            teluguName = teluguName
                .replace(/[a-zA-Z0-9_{}'":\[\],\-]/g, '') // Remove English chars and symbols
                .replace(/\s+/g, ' ') // Replace multiple spaces with single space
                .trim();
            
            // Only return if we have actual Telugu content
            if (teluguName && teluguName.length > 0) {
                return `• ${teluguName}`;
            }
        }
        
        return null;
    }).filter(Boolean);
    
    if (schemesList.length > 0) {
        schemesContainer.innerHTML = schemesList.join('<br>');
    } else {
        schemesContainer.innerHTML = 'ఇంకా పథకాలు కనుగొనలేదు';
    }
}

async function updateProfile(profileData) {
    await fetch("/update_profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profileData)
    });
    loadProfile();
}

// Load profile on page load
loadProfile();

// Refresh profile every 5 seconds to show updates
setInterval(loadProfile, 5000);

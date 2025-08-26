const express = require("express");
const qrcode = require("qrcode-terminal");
const dns = require("dns");
const axios = require("axios");
const fs = require("fs");
const path = require("path");

const app = express();
const port = process.env.NODEJS_TOOLS_PORT || 3000;

app.use(express.json());

let githubCache = new Map();
const GITHUB_CACHE_DURATION = 24 * 60 * 60 * 1000; // 24 hours

function loadBanner(type) {
    const bannersDir = path.join(__dirname, "../banners");
    
    if (type === "welcome") {
        try {
            const logo = fs.readFileSync(path.join(bannersDir, "logo_banner.txt"), "utf8");
            const welcome = fs.readFileSync(path.join(bannersDir, "welcome_banner.txt"), "utf8");
            return logo + "\n\n" + welcome;
        } catch (error) {
            console.error(`Error loading welcome banners:`, error);
            return "Welcome to EXPOSE!";
        }
    }
    
    try {
        const bannerFile = path.join(bannersDir, `${type}_banner.txt`);
        return fs.readFileSync(bannerFile, "utf8");
    } catch (error) {
        console.error(`Error loading ${type} banner:`, error);
        return "";
    }
}

async function checkGitHubStargazer(username) {
    const cacheKey = `${username}_star`;
    const now = Date.now();
    const githubRepo = process.env.GITHUB_REPOSITORY || 'exposesh/expose-server';
    
    if (githubCache.has(cacheKey)) {
        const cached = githubCache.get(cacheKey);
        if (now - cached.timestamp < GITHUB_CACHE_DURATION) {
            return cached.isStargazer;
        }
    }
    
    try {
        const response = await axios.get(`https://api.github.com/repos/${githubRepo}/stargazers`, {
            headers: {
                'User-Agent': 'EXPOSE-Tool'
            }
        });
        
        const isStargazer = response.data.some(stargazer => stargazer.login === username);
        
        githubCache.set(cacheKey, {
            isStargazer,
            timestamp: now
        });
        
        return isStargazer;
    } catch (error) {
        console.error(`Error checking stargazer status for ${username}:`, error);
        
        if (githubCache.has(cacheKey)) {
            return githubCache.get(cacheKey).isStargazer;
        }
        
        return false;
    }
}

async function fetchGitHubSSHKeys(username) {
    const cacheKey = `${username}_keys`;
    const now = Date.now();
    
    if (githubCache.has(cacheKey)) {
        const cached = githubCache.get(cacheKey);
        if (now - cached.timestamp < GITHUB_CACHE_DURATION) {
            return cached.keys;
        }
    }
    
    try {
        const response = await axios.get(`https://api.github.com/users/${username}/keys`, {
            headers: {
                'User-Agent': 'EXPOSE-Tool'
            }
        });
        
        const keys = response.data.map(key => key.key);
        
        githubCache.set(cacheKey, {
            keys,
            timestamp: now
        });
        
        return keys;
    } catch (error) {
        console.error(`Error fetching SSH keys for ${username}:`, error);
        
        if (githubCache.has(cacheKey)) {
            return githubCache.get(cacheKey).keys;
        }
        
        return [];
    }
}

app.get("/generateQRCode", async (req, res) => {
    const url = req.query.url;

    try {
        if (!url) {
            res.status(400).send("URL is required");
            return;
        }

        const qrCodeText = await generateQRCode(url);

        res.status(200).json({
            qrCodeText: qrCodeText
        });
    } catch (error) {
        console.error("Error generating QR code:", error);
        res.status(500).send("Internal server error");
    }
});

function generateQRCode(url) {
    return new Promise((resolve, reject) => {
        qrcode.generate(url, {
            small: true
        }, (qrcode) => {
            resolve(qrcode);
        });
    });
}

app.get("/getAllInstancesIPv6", async (req, res) => {
    const flydotioAppName = process.env.FLYDOTIO_APP_NAME;

    try {
        const instances = await getAllInstances(flydotioAppName);

        res.status(200).json({
            instances: instances
        });
    } catch (error) {
        console.error("Error getting all instances:", error);
        res.status(500).send("Internal server error");
    }
});

async function getAllInstances(flydotioAppName) {
    try {
        const records = await dns.promises.resolve6(`global.${flydotioAppName}.internal`);
        return records;
    } catch (error) {
        console.log(error);
        return {
            "error": error
        };
    }
}

app.get("/addToNginxCache", async (req, res) => {
    const flydotioAppName = process.env.FLYDOTIO_APP_NAME;
    const appname = req.query.app_name;
    const ipv6 = req.query.ipv6;

    try {
        if (!appname) {
            res.status(400).send("app_name is required");
            return;
        }

        if (!ipv6) {
            res.status(400).send("ipv6 is required");
            return;
        }

        const instances = await getAllInstances(flydotioAppName);

        const requests = instances.map(async (instanceIPv6) => {
            const url = `http://[${instanceIPv6}]:8081/cache/add?app_name=${appname}&ipv6=${ipv6}`;
            await axios.get(url);
        });

        await Promise.all(requests);

        res.status(200).json({
            message: "Cache add requests sent successfully",
        });
    } catch (error) {
        console.error("Error updating cache:", error);
        res.status(500).send("Internal server error");
    }
});

app.get("/removeFromNginxCache", async (req, res) => {
    const flydotioAppName = process.env.FLYDOTIO_APP_NAME;
    const appname = req.query.app_name;

    try {
        if (!appname) {
            res.status(400).send("app_name is required");
            return;
        }

        const instances = await getAllInstances(flydotioAppName);

        const requests = instances.map(async (instanceIPv6) => {
            const url = `http://[${instanceIPv6}]:8081/cache/remove?app_name=${appname}`;
            await axios.get(url);
        });

        await Promise.all(requests);

        res.status(200).json({
            message: "Cache remove requests sent successfully",
        });
    } catch (error) {
        console.error("Error updating cache:", error);
        res.status(500).send("Internal server error");
    }
});

app.get("/checkIfTunnelExists", async (req, res) => {
    const flydotioAppName = process.env.FLYDOTIO_APP_NAME;
    const appname = req.query.app_name;

    try {
        if (!appname) {
            res.status(400).send("app_name is required");
            return;
        }

        const instances = await getAllInstances(flydotioAppName);

        let tunnelFound = false;
        let foundIPv6;

        const requests = instances.map(async (instanceIPv6) => {
            const url = `http://[${instanceIPv6}]:8081/check/tunnel?app_name=${appname}`;

            try {
                const response = await axios.get(url);

                if (response.status === 200) {
                    tunnelFound = true;
                    foundIPv6 = instanceIPv6;
                }
            } catch (error) {
                if (error.response && error.response.status === 404) {
                    return;
                }
                throw error;
            }
        });

        await Promise.all(requests);

        if (tunnelFound) {
            res.status(200).json({
                message: "Tunnel found on one of the instances",
                ipv6: foundIPv6
            });
        } else {
            res.status(404).json({
                message: "Tunnel not found on any instance",
            });
        }
    } catch (error) {
        console.error("Error checking tunnel:", error);
        res.status(500).send("Internal server error");
    }
});

app.get("/getBanner", async (req, res) => {
    const type = req.query.type;

    if (!type) {
        res.status(400).send("Type is required");
        return;
    }

    const banner = loadBanner(type);
    
    if (banner) {
        res.status(200).json({
            bannerContent: banner
        });
    } else {
        res.status(400).send(`Unhandled banner type: ${type}`);
    }
});

app.get("/keyMatchesAccount", async (req, res) => {
    const { username, key } = req.query;

    try {
        const sshKeys = await fetchGitHubSSHKeys(username);
        const isStargazer = await checkGitHubStargazer(username);

        if (sshKeys.includes(key)) {
            console.log(`Key matches account ${username}`);
            if (isStargazer) {
                console.log(`User ${username} is a stargazer`);
            }
            res.json({
                matches: true,
                isStargazer
            });
        } else {
            console.log(`Key does not match account ${username}`);
            res.json({
                matches: false,
                isStargazer: false
            });
        }
    } catch (error) {
        console.error(`Error checking SSH keys for ${username}: ${error}`);
        res.json({
            matches: false,
            isStargazer: false
        });
    }
});

app.get("/isUserStargazer", async (req, res) => {
    const { username } = req.query;

    try {
        const isStargazer = await checkGitHubStargazer(username);

        if (isStargazer) {
            console.log(`User ${username} is a stargazer`);
        } else {
            console.log(`User ${username} is not a stargazer`);
        }
        res.json({
            isStargazer
        });
    } catch (error) {
        console.error(`Error checking stargazer status for ${username}: ${error}`);
        res.json({
            isStargazer: false
        });
    }
});

app.listen(port, () => {
    console.log(`EXPOSE tools is running on port ${port}`);
});
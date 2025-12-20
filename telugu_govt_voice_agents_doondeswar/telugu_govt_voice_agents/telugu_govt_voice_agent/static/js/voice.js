/**
 * Telugu Voice Handler - STT and TTS Implementation
 * Integrates with existing Telugu Government Voice Agent
 */
class TeluguVoiceHandler {
    constructor() {
        this.recognition = null;
        this.synthesis = window.speechSynthesis;
        this.isListening = false;
        this.isSpeaking = false;
        this.currentUtterance = null;
        this.voiceEnabled = true;
        this.selectedVoice = null;
        this.statusElement = null;
        
        this.initializeSpeechRecognition();
        this.loadVoices();
        this.setupEventHandlers();
    }

    /**
     * Initialize Speech Recognition for Telugu
     */
    initializeSpeechRecognition() {
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            console.error('Speech recognition not supported');
            this.showFallbackMessage();
            return;
        }

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        this.recognition = new SpeechRecognition();
        
        // Configure for Telugu
        this.recognition.lang = 'te-IN';
        this.recognition.continuous = false;
        this.recognition.interimResults = false;
        this.recognition.maxAlternatives = 1;

        // Set up event handlers
        this.recognition.onstart = () => {
            this.isListening = true;
            this.updateVoiceStatus('వింటున్నాను...', 'listening');
            this.updateMicrophoneButton(true);
        };

        this.recognition.onresult = (event) => {
            const result = event.results[0][0];
            const teluguText = result.transcript;
            const confidence = result.confidence || 0.5;
            this.handleSpeechResult(teluguText, confidence);
        };

        this.recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            this.isListening = false;
            this.handleSpeechError(event.error);
            this.updateMicrophoneButton(false);
        };

        this.recognition.onend = () => {
            this.isListening = false;
            this.updateMicrophoneButton(false);
            this.updateVoiceStatus('వినడం ముగిసింది', 'success');
        };
    }

    /**
     * Load and select best Telugu voice
     */
    loadVoices() {
        const loadVoicesImpl = () => {
            const voices = this.synthesis.getVoices();
            if (voices.length === 0) {
                setTimeout(loadVoicesImpl, 100);
                return;
            }
            this.selectBestTeluguVoice(voices);
        };

        // Load voices immediately and on voiceschanged event
        loadVoicesImpl();
        this.synthesis.addEventListener('voiceschanged', loadVoicesImpl);
    }

    /**
     * Select best available Telugu voice
     */
    selectBestTeluguVoice(voices) {
        // Priority: Telugu female → Telugu any → Hindi → English Indian → Default
        this.selectedVoice = voices.find(v => 
            v.lang.includes('te-IN') && v.name.toLowerCase().includes('female')
        );
        
        if (!this.selectedVoice) {
            this.selectedVoice = voices.find(v => v.lang.includes('te-IN'));
        }
        
        if (!this.selectedVoice) {
            this.selectedVoice = voices.find(v => v.lang.includes('te'));
        }
        
        if (!this.selectedVoice) {
            this.selectedVoice = voices.find(v => v.lang.includes('hi-IN'));
        }
        
        if (!this.selectedVoice) {
            this.selectedVoice = voices.find(v => v.lang.includes('en-IN'));
        }

        console.log('Selected voice:', this.selectedVoice?.name || 'Default');
    }

    /**
     * Set up event handlers for UI elements
     */
    setupEventHandlers() {
        // Check if DOM is already loaded
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                this.bindUIElements();
            });
        } else {
            // DOM is already loaded
            this.bindUIElements();
        }
    }

    /**
     * Bind voice controls to UI elements
     */
    bindUIElements() {
        console.log('Binding UI elements...');
        
        // Microphone button (now in input area)
        const micButton = document.getElementById('mic-button');
        console.log('Mic button found:', micButton);
        if (micButton) {
            micButton.addEventListener('click', (e) => {
                e.preventDefault();
                console.log('Mic button clicked');
                this.toggleListening();
            });
        } else {
            console.error('Microphone button not found!');
        }

        // Speaker test button
        const speakerButton = document.getElementById('speaker-button');
        if (speakerButton) {
            speakerButton.addEventListener('click', () => this.testSpeech());
        }

        // Stop button
        const stopButton = document.getElementById('stop-button');
        if (stopButton) {
            stopButton.addEventListener('click', () => this.stopAllVoiceActivity());
        }

        // Voice toggle
        const voiceToggle = document.getElementById('voice-toggle');
        if (voiceToggle) {
            voiceToggle.addEventListener('click', () => this.toggleVoiceEnabled());
        }

        // Status element
        this.statusElement = document.getElementById('voice-status');
    }

    /**
     * Start listening for speech
     */
    startListening() {
        if (!this.recognition) {
            this.showFallbackMessage();
            return;
        }

        if (this.isListening) {
            return;
        }

        // Stop any current speech
        this.stopSpeaking();

        try {
            this.recognition.start();
        } catch (error) {
            console.error('Error starting recognition:', error);
            this.updateVoiceStatus('వినడం ప్రారంభించలేకపోయింది', 'error');
        }
    }

    /**
     * Stop listening for speech
     */
    stopListening() {
        if (this.recognition && this.isListening) {
            this.recognition.stop();
        }
    }

    /**
     * Toggle listening state
     */
    toggleListening() {
        if (this.isListening) {
            this.stopListening();
        } else {
            this.startListening();
        }
    }

    /**
     * Speak Telugu text
     */
    speakTelugu(text) {
        if (!this.voiceEnabled || !text) {
            return;
        }

        // Stop any current speech
        this.stopSpeaking();

        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = 'te-IN';
        utterance.rate = 0.8;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;

        if (this.selectedVoice) {
            utterance.voice = this.selectedVoice;
        }

        utterance.onstart = () => {
            this.isSpeaking = true;
            this.updateVoiceStatus('మాట్లాడుతున్నాను...', 'speaking');
        };

        utterance.onend = () => {
            this.isSpeaking = false;
            this.currentUtterance = null;
            this.updateVoiceStatus('మాట్లాడడం పూర్తయింది', 'success');
        };

        utterance.onerror = (event) => {
            console.error('Speech synthesis error:', event);
            this.isSpeaking = false;
            this.currentUtterance = null;
            this.updateVoiceStatus('మాట్లాడడంలో లోపం', 'error');
        };

        this.currentUtterance = utterance;
        this.synthesis.speak(utterance);
    }

    /**
     * Stop current speech
     */
    stopSpeaking() {
        if (this.synthesis.speaking) {
            this.synthesis.cancel();
        }
        this.isSpeaking = false;
        this.currentUtterance = null;
    }

    /**
     * Stop all voice activity
     */
    stopAllVoiceActivity() {
        this.stopListening();
        this.stopSpeaking();
        this.updateVoiceStatus('అన్ని వాయిస్ కార్యకలాపాలు ఆపబడ్డాయి', 'info');
    }

    /**
     * Test speech with sample Telugu text
     */
    testSpeech() {
        const testText = "నమస్కారం! నేను మీ ప్రభుత్వ పథకాల సహాయకుడిని. మీ అర్హత ఆధారంగా ప్రభుత్వ పథకాలను గుర్తించి దరఖాస్తు చేయడంలో సహాయం చేస్తాను.";
        this.speakTelugu(testText);
    }

    /**
     * Toggle voice functionality
     */
    toggleVoiceEnabled() {
        this.voiceEnabled = !this.voiceEnabled;
        
        if (!this.voiceEnabled) {
            this.stopAllVoiceActivity();
        }

        this.updateVoiceToggleButton();
        this.updateVoiceStatus(
            this.voiceEnabled ? 'వాయిస్ ఆన్ చేయబడింది' : 'వాయిస్ ఆఫ్ చేయబడింది',
            this.voiceEnabled ? 'success' : 'info'
        );
    }

    /**
     * Handle speech recognition result
     */
    handleSpeechResult(text, confidence) {
        console.log('Speech result:', text, 'Confidence:', confidence);
        
        // Display confidence if available
        if (confidence) {
            this.updateVoiceStatus(`వినబడింది (${Math.round(confidence * 100)}% నమ్మకం)`, 'success');
        }

        // Send to chat - integrate with existing chat functionality
        this.sendVoiceMessage(text, confidence);
    }

    /**
     * Handle speech recognition errors
     */
    handleSpeechError(error) {
        let errorMessage = 'వాయిస్ లోపం';
        
        switch (error) {
            case 'no-speech':
                errorMessage = 'వినిపించలేదు. దయచేసి మళ్ళీ ప్రయత్నించండి.';
                break;
            case 'audio-capture':
                errorMessage = 'మైక్రోఫోన్ సమస్య. దయచేసి మైక్రోఫోన్ కనెక్షన్ చూడండి.';
                break;
            case 'not-allowed':
                errorMessage = 'మైక్రోఫోన్ అనుమతి అవసరం. దయచేసి అనుమతి ఇవ్వండి.';
                this.showPermissionHelp();
                break;
            case 'network':
                errorMessage = 'నెట్‌వర్క్ సమస్య. దయచేసి మళ్ళీ ప్రయత్నించండి.';
                break;
            default:
                errorMessage = `వాయిస్ లోపం: ${error}`;
        }

        this.updateVoiceStatus(errorMessage, 'error');
    }

    /**
     * Send voice message to chat
     */
    async sendVoiceMessage(text, confidence) {
        try {
            // Add voice indicator to message
            this.addUserMessage(text, true, confidence);

            // Send to backend
            const response = await fetch('/agent', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    text: text,
                    voice_input: true,
                    confidence: confidence
                })
            });

            const data = await response.json();
            
            // Display bot response
            this.addBotMessage(data.response);

            // Auto-speak bot response if enabled
            if (this.voiceEnabled && data.auto_speak !== false) {
                setTimeout(() => {
                    this.speakTelugu(data.response);
                }, 500); // Small delay for better UX
            }

        } catch (error) {
            console.error('Error sending voice message:', error);
            this.updateVoiceStatus('సందేశం పంపడంలో లోపం', 'error');
        }
    }

    /**
     * Add user message to chat
     */
    addUserMessage(text, isVoice = false, confidence = null) {
        const chatBox = document.querySelector('.chat-box');
        if (!chatBox) return;

        const messageDiv = document.createElement('div');
        messageDiv.className = 'user-msg';
        
        let confidenceText = '';
        if (isVoice && confidence) {
            confidenceText = ` <span class="confidence">(${Math.round(confidence * 100)}%)</span>`;
        }
        
        messageDiv.innerHTML = `
            ${isVoice ? '🎤 ' : ''}${text}${confidenceText}
        `;
        
        chatBox.appendChild(messageDiv);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    /**
     * Add bot message to chat
     */
    addBotMessage(text) {
        const chatBox = document.querySelector('.chat-box');
        if (!chatBox) return;

        const messageDiv = document.createElement('div');
        messageDiv.className = 'bot-msg';
        messageDiv.innerHTML = `
            ${text}
            <button class="speak-btn" onclick="voiceHandler.speakTelugu('${text.replace(/'/g, '\\\'')}')" title="మాట్లాడు">🔊</button>
        `;
        
        chatBox.appendChild(messageDiv);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    /**
     * Update voice status display
     */
    updateVoiceStatus(message, type = 'info') {
        if (this.statusElement) {
            this.statusElement.textContent = message;
            this.statusElement.className = `voice-status ${type}`;
        }
        
        // Auto-clear status after 3 seconds for non-error messages
        if (type !== 'error') {
            setTimeout(() => {
                if (this.statusElement) {
                    this.statusElement.textContent = '';
                    this.statusElement.className = 'voice-status';
                }
            }, 3000);
        }
    }

    /**
     * Update microphone button state
     */
    updateMicrophoneButton(isListening) {
        const micButton = document.getElementById('mic-button');
        if (micButton) {
            micButton.classList.toggle('listening', isListening);
            micButton.title = isListening ? 'వినడం ఆపు' : 'వినడం ప్రారంభించు';
        }
    }

    /**
     * Update voice toggle button
     */
    updateVoiceToggleButton() {
        const voiceToggle = document.getElementById('voice-toggle');
        if (voiceToggle) {
            voiceToggle.textContent = this.voiceEnabled ? '🔊' : '🔇';
            voiceToggle.title = this.voiceEnabled ? 'వాయిస్ ఆఫ్ చేయి' : 'వాయిస్ ఆన్ చేయి';
        }
    }

    /**
     * Show fallback message for unsupported browsers
     */
    showFallbackMessage() {
        this.updateVoiceStatus('మీ బ్రౌజర్ వాయిస్ రికగ్నిషన్‌ను సపోర్ట్ చేయదు', 'error');
    }

    /**
     * Show permission help
     */
    showPermissionHelp() {
        const helpMessage = `
            మైక్రోఫోన్ అనుమతి ఇవ్వడానికి:
            1. బ్రౌజర్ చిహ్నంలో మైక్రోఫోన్ చిహ్నంపై క్లిక్ చేయండి
            2. "అనుమతించు" ఎంచుకోండి
            3. పేజీని రీలోడ్ చేయండి
        `;
        alert(helpMessage);
    }

    /**
     * Check if currently listening
     */
    isCurrentlyListening() {
        return this.isListening;
    }

    /**
     * Check if currently speaking
     */
    isCurrentlySpeaking() {
        return this.isSpeaking;
    }
}

// Initialize voice handler when DOM is ready
let voiceHandler;

// Multiple initialization attempts to ensure proper binding
function initializeVoiceHandler() {
    try {
        voiceHandler = new TeluguVoiceHandler();
        console.log('Voice handler initialized successfully');
        
        // Initialize UI bindings
        voiceHandler.bindUIElements();
        
        // Auto-greet user with Telugu welcome message
        setTimeout(() => {
            const welcomeMessage = "నమస్కారం! నేను మీ ప్రభుత్వ పథకాల సహాయకుడిని. మీ అర్హత ఆధారంగా ప్రభుత్వ పథకాలను గుర్తించి దరఖాస్తు చేయడంలో సహాయం చేస్తాను.";
            voiceHandler.addBotMessage(welcomeMessage);
            if (voiceHandler.voiceEnabled) {
                voiceHandler.speakTelugu(welcomeMessage);
            }
        }, 1000);
        
    } catch (error) {
        console.error('Failed to initialize voice handler:', error);
        // Retry after a short delay
        setTimeout(initializeVoiceHandler, 1000);
    }
}

// Try multiple ways to ensure initialization
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeVoiceHandler);
} else {
    initializeVoiceHandler();
}

// Fallback initialization
window.addEventListener('load', () => {
    if (!voiceHandler) {
        console.log('Fallback initialization...');
        initializeVoiceHandler();
    }
});

/**
 * Integrate voice with existing chat functionality
 */
function setupVoiceIntegration() {
    const inputField = document.querySelector('.input-area input');
    const sendButton = document.querySelector('.send-btn');
    
    if (inputField && sendButton) {
        // Handle send button click
        sendButton.addEventListener('click', () => {
            const text = inputField.value.trim();
            if (text) {
                sendMessage(text);
                inputField.value = '';
            }
        });
        
        // Handle Enter key
        inputField.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const text = inputField.value.trim();
                if (text) {
                    sendMessage(text);
                    inputField.value = '';
                }
            }
        });
    }
    
    // Handle quick action buttons
    const quickButtons = document.querySelectorAll('.quick-card button');
    quickButtons.forEach(button => {
        button.addEventListener('click', () => {
            const text = button.textContent;
            sendMessage(text);
        });
    });
}

/**
 * Send message to agent (enhanced version)
 */
async function sendMessage(text, isVoiceInput = false, confidence = null) {
    if (!text.trim()) return;
    
    try {
        // Add user message to chat
        voiceHandler.addUserMessage(text, isVoiceInput, confidence);
        
        // Send to backend
        const response = await fetch('/agent', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                text: text,
                voice_input: isVoiceInput,
                confidence: confidence
            })
        });
        
        const data = await response.json();
        
        // Add bot response to chat
        voiceHandler.addBotMessage(data.response);
        
        // Auto-speak if voice is enabled and not disabled for this response
        if (voiceHandler.voiceEnabled && data.auto_speak !== false) {
            setTimeout(() => {
                voiceHandler.speakTelugu(data.response);
            }, 500);
        }
        
    } catch (error) {
        console.error('Error sending message:', error);
        voiceHandler.updateVoiceStatus('సందేశం పంపడంలో లోపం', 'error');
    }
}
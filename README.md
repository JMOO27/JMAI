# OurCHAI (Our Character AI)

**Please note:** This project is a work in progress. The features described below are planned for implementation and are not necessarily available yet. This is not a usable product at this stage.

OurCHAI is a general-purpose AI interface designed for those who want to **pay only for what they use, without sacrificing their privacy.** This web application can be configured to run either locally on your machine or across your local network.

OurCHAI leverages OpenRouter's API to provide you (and your local users!) with the basic functionality found on nearly every AI platform, along with much more. By utilizing OpenRouter, you can customize your experience and access its extensive selection of over 500 AI models, each offering different capabilities and modalities, including voice, video, music, text, and images. Our goal is to coordinate these capabilities to deliver features and flexibility that traditional AI platforms often lack.

One of the biggest benefits of leveraging OpenRouter's API is its potential for privacy. Through specific API parameters and provider configurations, we can enforce Zero Data Retention (ZDR) where supported, restrict providers based on their data collection policies, and limit how your information is handled. The best part? You won't need to configure these settings yourself. OurCHAI is designed with privacy-focused defaults, prioritizing providers and configurations that minimize data retention and collection.

You'll also have the option to encrypt your stored conversations, or disable conversation storage entirely!

**Everything works out of the box. Have fun!**

## Some Planned Features Include:
- **Character AI Mode:** 
  * Includes a roleplay engine, leveraging stored story and character states to ensure a lively and accurate story.
  * Various sub-modes to keep things fun and fresh.
  * Smart Compaction keeps your stories cheap and fast.
- **Personal Information Firewall:**
  * Leverging DLP (Data Loss Prevention) technologies, each request will be locally scanned for PII (Personally Identifiable Information) to protect your data in depth. 
- **Learn / Teach / Test Mode:** 
  * Includes a learning engine that facilitates your learning through both visual, voice and text modalities. The engine keeps track of your goals, progress, and potential gaps, offering excellent remediation to cover those gaps.
- **Encrypt Everything!** 
  * Stored Conversations, Character Configurations, Custom Prompts are all encrypted, only decrypted when use is needed, otherwise completely safe and sound.
  * You can optionally choose a more secure method, such as using a Hardware Security Key to keep decryption keys completely away from the system.

And significantly more, I'll be sure to update this as the project goes on...

### Current TODO List is:
- Model and Build basic UI interface.
  



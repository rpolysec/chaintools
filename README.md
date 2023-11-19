# rpolysec Investigation Scripts

Various python scripts for investigating blockchain transactions. These are definitely broken as is and is a work in progress. Uploading as I go, hoping eventually this will be usable by more people then me.

Be kind. If you find this useuful or improve on it, please let me know. My motivation for making these open source is to reduce the bar for investigating blockchain thefts to hopefully encourage people to help victims who cannot afford expensive blockchain analytics firms.

# Try These First

There are several free and paid blockchain investigation tools and the scripts in this repo are NOT a substitute for those. If you want to get into blockchain investigations try these first:

- Meta Sleuth (https://metasleuth.io/)
- MistTrack (https://misttrack.io/)
- Breadcrumbs (https://www.breadcrumbs.app/)
- Chainalysis (https://www.chainalysis.com/)
- TRM (https://www.trmlabs.com/)
- Elliptic (https://www.elliptic.co/)

Let me know if I'm missing any.

# Why Create Python Scripts

Like many cyber security professionals my goto investigation style is a command prompt, python and a data source. Don't get me wrong, fancy UI's are great, but having to load up Etherscan or login to Chainalysis everytime I want to see a token balance isn't great. Also, sometimes I want to something that the existing tools just don't support, like tracing a specific set of tainted funds using FIFO or LIFO, or some other strategy.

As I write scripts I find useful I'll add them here as examples in case they can help other people with their custom investigation scripts.

# No Warranty, Experimental

These scripts are not always user friendly. They might not make sense. They might not be efficient. They won't scale to thousands of transactions. For a lot of small scale investigations none of that matters. They make sense to me, and I would expect most people to just grab snippets of code from here and build scripts that make sense to them.

# Lets talk

If you have thoughts, suggestions, or want to share your own scripts feel free to hit me up on Twitter, @rpolysec

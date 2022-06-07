# Digital Slide Archive

The [Digital Slide Archive][1] (DSA) is "a containerized web-based platform for the analysis, visualization, management and
annotation of whole-slide digital pathology imaging data".
It is an open-source project based on [Kitware][11]'s data management platform [Girder][10].

## Azure deployment

We have deployed the DSA on [Azure][2] to visualize our data and interpret our models and experiments.
Below are instructions to replicate our deployment using your own data.

### Host

The first step is [creating a Linux virtual machine][4] (VM) to host the DSA.
The code can be [downloaded from GitHub][5] and run using [Docker][6].
By default, the application runs at port 8080.
To use HTTPS, an SSL certificate must be obtained and port 443 may be specified instead within the Docker configuration.
The DSA uses [Cherrypy][8] as the underlying server engine.
Therefore, Cherrypy must be [configured][9] to use the SSL certificate installed in the VM.
Ports in a VM can be opened using [network security group rules][7].

### Storage

The datasets we use are securely stored in [Azure Blob Storage][3] containers.
Containers can be mounted on the host machine using [BlobFuse][13] and connected to Girder using [assetstores].

### Authentication

We have [added][14] Microsoft as a provider in the [OAuth2 Login][15] plugin for Girder.
An app must be [registered][16] so that [Azure Active Directory][17] (Azure AD) can be used for authentication.

### Authorization

User [permissions][18] can be set to different data collections in an assetstore, to maximize protection of sensitive data.

## Visualizing Azre Machine Learning results

The [Girder RESTful API][19] may be used to upload annotations to DSA items programmatically.
A usage case is creating annotations

[1]: https://digitalslidearchive.github.io/digital_slide_archive/
[2]: https://azure.microsoft.com/
[3]: https://azure.microsoft.com/services/storage/blobs/
[4]: https://docs.microsoft.com/azure/virtual-machines/linux/quick-create-portal
[5]: https://github.com/DigitalSlideArchive/digital_slide_archive/blob/master/devops/README.rst
[6]: https://www.docker.com/
[7]: https://docs.microsoft.com/en-us/azure/virtual-machines/windows/nsg-quickstart-portal
[8]: https://docs.cherrypy.dev/en/latest/
[9]: https://docs.cherrypy.dev/en/latest/deploy.html#ssl-support
[10]: https://girder.readthedocs.io/
[11]: https://www.kitware.com/
[12]: https://girder.readthedocs.io/en/latest/user-guide.html#assetstores
[13]: https://github.com/Azure/azure-storage-fuse
[14]: https://github.com/girder/girder/pull/3393
[15]: https://girder.readthedocs.io/en/latest/plugins.html#oauth2-login
[16]: https://docs.microsoft.com/en-us/azure/active-directory/develop/quickstart-register-app
[17]: https://azure.microsoft.com/en-us/services/active-directory/
[18]: https://girder.readthedocs.io/en/stable/user-guide.html#permissions
[19]: https://girder.readthedocs.io/en/latest/api-docs.html
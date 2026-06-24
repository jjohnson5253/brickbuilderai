# Notes
 - This app creates a docker image that uses sam3d image-to-3d model but stops short of the GLB generation because only voxels are needed for lego conversion. This code is in `/serverless` and code for calling the hosted docker image as a serverless endpoint on runpod is in route.ts
 - you can use /frontend to test
### uploading to docker
 - `cd serverless`
 - `depot build --platform linux/amd64 --tag jjohnson5253/manifold-sam3d:latest --push .`
 - force refresh for workers to use new image in runpod. Manage->new release->change name and deploy->then change name back and deploy (runpod needs image name to change but we didn't upload a new tag version)

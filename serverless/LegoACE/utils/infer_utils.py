from PIL import Image
import os
from pathlib import Path

def load_input_images_from_output_dir(input_dir):
    images = {}
    for filename in input_dir.glob("*.png"):
        img = Image.open(filename)
        images[filename.stem] = img
    
    return images

def load_input_images_from_output_dir_mv(input_dir):
    images = {}
    for filename in input_dir.glob("*.png"):
        if filename.stem.endswith("_0"):
            img = Image.open(filename).resize((512, 512))
            images[filename.stem.split('_')[0]] = img
    
    return images

def load_output_images_from_output_dir(output_dir):
    images = {}
    # for image_id in output_dir.iterdir():
    for img_path in output_dir.glob("*.png"):
        img = Image.open(img_path)
        images[img_path.stem] = img
    return images

def load_output_images_from_output_dir_with_repeat(output_dir):
    images = {}
    # for image_id in output_dir.iterdir():
    for img_path in output_dir.glob("*.png"):
        img = Image.open(img_path)
        image_name = img_path.stem
        input_id = image_name.split("-")[0]
        repeat_id = image_name.split("-")[1]
        if not input_id in images:
            images[input_id] = {}

        images[input_id][repeat_id] = img 
    return images


def create_image_grid(input_images, output_images, images_per_row):
    # Get the filenames sorted to ensure they match in order
    filenames = sorted(input_images.keys())
    
    # Get the size of the images (assuming all images are the same size)
    img_width, img_height = input_images[filenames[0]].size
    
    assert images_per_row % 2 == 0, "images_per_row must be an even number"
    # Calculate number of rows
    rows = len(filenames) // (images_per_row // 2)
    if len(filenames) % images_per_row != 0:
        rows += 1

    cols = images_per_row  # Since we're placing images from both directories together (side by side)

    # Calculate the total size of the output image
    total_width = img_width * cols
    total_height = img_height * rows

    # Create a new image to paste all the images into
    new_img = Image.new('RGB', (total_width, total_height))

    # Place images in the grid
    y_offset = 0
    x_offset = 0
    for i, filename in enumerate(filenames):
        img1 = input_images[filename]
        if filename in output_images:
            img2 = output_images[filename]
        else:
            img2 = Image.new('RGB', (img_width, img_height), (255, 255, 255))
        
        # Paste image 1 from the first output_dir
        new_img.paste(img1, (x_offset, y_offset))
        x_offset += img_width
        # Paste image 2 from the second output_dir
        new_img.paste(img2, (x_offset, y_offset))
        x_offset += img_width
        if x_offset >= total_width:
            x_offset = 0
            y_offset += img_height

    # Save the resulting image
    return new_img
    # new_img.save(output_path)
    # print(f"Image grid saved to {output_path}")

def create_image_grid_with_repeat(input_images, output_images, repeat, samples_per_row=2):
    filenames = sorted(input_images.keys())
    
    # Get the size of the images (assuming all images are the same size)
    img_width, img_height = input_images[filenames[0]].size
    
    # assert images_per_row % 2 == 0, "images_per_row must be an even number"
    # Calculate number of rows
    rows = len(filenames) // samples_per_row
    if len(filenames) % samples_per_row != 0:
        rows += 1

    cols = samples_per_row * (1 + repeat)  # Since we're placing images from both directories together (side by side)

    # Calculate the total size of the output image
    total_width = img_width * cols
    total_height = img_height * rows

    # Create a new image to paste all the images into
    new_img = Image.new('RGB', (total_width, total_height))

    # Place images in the grid
    y_offset = 0
    x_offset = 0
    for i, filename in enumerate(filenames):
        img1 = input_images[filename]
        new_img.paste(img1, (x_offset, y_offset))
        # Paste image 1 from the first output_dir
        x_offset += img_width
        if filename in output_images:
            for repeat_id in range(repeat):
                if str(repeat_id) in output_images[filename]:
                    img = output_images[filename][str(repeat_id)]
                else:
                    img = Image.new('RGB', (img_width, img_height), (255, 255, 255))
                # Paste image 2 from the second output_dir
                new_img.paste(img, (x_offset, y_offset))
                x_offset += img_width
                if x_offset >= total_width:
                    x_offset = 0
                    y_offset += img_height
        else:
            raise RuntimeError("no output")

    # Save the resulting image
    return new_img

def make_compare(input_dir, output_dir, images_per_row=4):
    # Load images from both directories
    input_images = load_input_images_from_output_dir(input_dir)
    output_images = load_output_images_from_output_dir(output_dir)
    # Create the image grid and save it
    image_grid = create_image_grid(input_images, output_images, images_per_row=images_per_row)
    return image_grid

def make_compare_mv(input_dir, output_dir, images_per_row=4):
    # Load images from both directories
    input_images = load_input_images_from_output_dir_mv(input_dir)
    output_images = load_output_images_from_output_dir(output_dir)
    # Create the image grid and save it
    image_grid = create_image_grid(input_images, output_images, images_per_row=images_per_row)
    return image_grid

def make_compare_with_repeat(input_dir, out_dir, repeat, samples_per_row=2):
    input_images = load_input_images_from_output_dir(input_dir)
    output_images = load_output_images_from_output_dir_with_repeat(out_dir)
    image_grid = create_image_grid_with_repeat(input_images, output_images, repeat=repeat, samples_per_row=samples_per_row)
    return image_grid

def make_compare_with_repeat_mv(input_dir, out_dir, repeat, samples_per_row=2):
    input_images = load_input_images_from_output_dir_mv(input_dir)
    output_images = load_output_images_from_output_dir_with_repeat(out_dir)
    image_grid = create_image_grid_with_repeat(input_images, output_images, repeat=repeat, samples_per_row=samples_per_row)
    return image_grid

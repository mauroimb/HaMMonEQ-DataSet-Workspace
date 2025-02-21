from pathlib import Path
import json
import random
import os
from PIL import Image, ImageDraw

class Project:
    def __init__(self, project_path, json_file=None):

        # Convert the path to a Path object and verify its validity
        self.path = Path(project_path)
        if not self.path.exists() or not self.path.is_dir():
            raise ValueError(f"The provided path '{project_path}' is not valid or is not a directory.")


        if json_file:
            # If a specific JSON file is provided, verify its existence
            self.json_file = self.path / json_file
            if not self.json_file.exists() or not self.json_file.is_file():
                raise ValueError(f"The specified JSON file '{json_file}' does not exist in the directory.")
        else:
            # Find JSON file(s) in the directory
            json_files = list(self.path.glob('*.json'))
            # If no JSON file is specified, check for exactly one JSON file
            if len(json_files) == 1:
                self.json_file = json_files[0]
            else:
                raise ValueError("No JSON file found or multiple JSON files present. Please specify the JSON file explicitly.")
        
        # Load JSON data
        with open(self.json_file, 'r') as f:
            self.data = json.load(f)
        
        self.analyze_annotations()
        self.assign_ids_and_colors()

    def analyze_annotations(self):
        # Initialize counters and storage
        self.annotation_count = 0
        self.annotations = {}

        # Iterate over each task in the data
        for task in self.data:
            for result in task["annotations"][0]["result"]:
                self.annotation_count += 1
                annotation_type = result["type"]

                if annotation_type not in self.annotations:
                    self.annotations[annotation_type] = set()  # Initialize set for new types
                
                value = result["value"]
                for p in value:
                    if p in self.annotations:
                        if len(value[p])>1:
                            raise ValueError('value[p] must be a list with one element')
                        self.annotations[p].update(value[p])

    def assign_ids_and_colors(self):
        self.ids_and_colors = {"polygonlabels": {}, "rectanglelabels": {}}

        # Function to generate random color
        def random_color():
            return "#%06x" % random.randint(0, 0xFFFFFF)

        # Assign IDs and colors to polygonlabels
        for idx, label in enumerate(self.annotations.get("polygonlabels", [])):
            self.ids_and_colors["polygonlabels"][label] = {
                "id": idx,
                "color": random_color()
            }

        # Assign IDs and colors to rectanglelabels
        for idx, label in enumerate(self.annotations.get("rectanglelabels", [])):
            self.ids_and_colors["rectanglelabels"][label] = {
                "id": idx,
                "color": random_color()
            }

        print('randomly assigned colors and ids to classes. Manually edit self.ids_and_colors for your convenience')

    @classmethod
    def create_mask(cls, image_size, polygons, color=1):
        mask = Image.new('L', image_size, 0)
        draw = ImageDraw.Draw(mask)
        for polygon in polygons:
            points = [(point[0], point[1]) for point in polygon]
            draw.polygon(points, outline=color, fill=color)
        return mask
    

    def export_masks(self, annotation_class=False, color=False, melt=False):
        dirname = "masks"
        if color: dirname += "-color"
        if (annotation_class): dirname += f"-{annotation_class}"
        if melt: dirname += '-melt'
        
        output_dir = self.path / dirname
        os.makedirs(output_dir, exist_ok=True)

        for item in self.data:
            raw_image_name = Path(item.get('data', {}).get('image', f'image_{item["id"]}')).name
            image_name = raw_image_name.split('-')[1] if '-' in raw_image_name else raw_image_name

            polygons_by_class = {}
            for annotation in item.get('annotations', []):
                for result in annotation.get('result', []):
                    if result['type'] == 'polygonlabels':
                        labels = result['value']['polygonlabels']
                        assert len(labels) == 1, 'wrong number of labels per result'
                        label = labels[0]

                        if ((annotation_class == False) or (label == annotation_class)) : 
                            image_size = (result.get('original_width'), result.get('original_height'))
                            points = result['value']['points']
                            abs_points = [(int(x * image_size[0] / 100), int(y * image_size[1] / 100)) for x, y in points]

                            if label not in polygons_by_class:
                                polygons_by_class[label] = []
                            polygons_by_class[label].append(abs_points)

            if polygons_by_class:
                mode = 'RGB' if color else 'L'
                mask = Image.new(mode, image_size, (0, 0, 0) if color else 0)
                draw = ImageDraw.Draw(mask)

                for clas in polygons_by_class:
                    if melt:
                        col = "#FFFFFF" if color else 1
                    else:
                        col = self.ids_and_colors['polygonlabels'][clas]['color'] if color else self.ids_and_colors['polygonlabels'][clas]['id'] 
                    for polygon in polygons_by_class[clas]:
                        draw.polygon(polygon, outline=col, fill=col)

                mask.save(output_dir / f"{image_name.split('.')[0]}.png")

        print("✅ Multiclass masks exported successfully!")


    def superposition(self, mask_dirs, alpha=0.5):
        """
        Overlays masks on the original images.

        Args:
            mask_dirs (list): List of subfolders containing the masks.
            alpha (float): Transparency level for the overlay (0.0 - completely transparent, 1.0 - fully opaque).
        """
        img_dir = self.path / "img"
        output_dir = self.path / "superposition"
        output_dir.mkdir(exist_ok=True)

        for image_file in img_dir.glob("*.*"):  # Supports all image formats
            original_image = Image.open(image_file).convert("RGBA")
            image_base_name = image_file.stem  # File name without extension

            # Create an empty image for the overlay
            overlay = Image.new("RGBA", original_image.size, (0, 0, 0, 0))

            for mask_dir in mask_dirs:
                mask_dir_path = self.path / mask_dir
                # Search for the mask matching the base name of the image
                mask_files = list(mask_dir_path.glob(f"{image_base_name}*.png"))

                for mask_path in mask_files:
                    if mask_path.exists():
                        mask = Image.open(mask_path).convert("RGBA")

                        # Apply transparency only to non-transparent pixels
                        mask_data = mask.getdata()
                        new_data = []

                        for item in mask_data:
                            # Apply alpha only if the pixel is not fully transparent
                            if item[:3] != (0, 0, 0):  # Non-black pixels considered as mask
                                new_data.append((item[0], item[1], item[2], int(255 * alpha)))
                            else:
                                new_data.append((0, 0, 0, 0))

                        mask.putdata(new_data)

                        # Overlay the mask
                        overlay = Image.alpha_composite(overlay, mask)

            # Combine the original image with the overlay
            final_image = Image.alpha_composite(original_image, overlay)

            # Save the resulting image
            final_image.convert("RGB").save(output_dir / f"{image_base_name}_superposed.jpg")

        print("✅ Superposition completed successfully!")


    def export_rectangle_masks(self, border_thickness=3):
        """
        Export PNG images with rectangles drawn for each original image.

        Args:
            border_thickness (int): Thickness of the rectangle border.
        """
        output_dir = self.path / "rectangle_masks"
        output_dir.mkdir(exist_ok=True)

        img_dir = self.path / "img"

        for item in self.data:
            raw_image_name = Path(item.get('data', {}).get('image', f'image_{item["id"]}')).name
            image_name = raw_image_name.split('-')[1] if '-' in raw_image_name else raw_image_name

            image_path = img_dir / image_name
            if not image_path.exists():
                print(f"⚠️ Image {image_name} not found. Skipping.")
                continue

            original_image = Image.open(image_path).convert("RGBA")
            draw = ImageDraw.Draw(original_image)

            for annotation in item.get('annotations', []):
                for result in annotation.get('result', []):
                    if result['type'] == 'rectanglelabels':
                        rect = result['value']
                        labels = rect['rectanglelabels']
                        assert len(labels) == 1, 'Wrong number of labels per rectangle'
                        label = labels[0]

                        # Absolute coordinates
                        image_size = (result.get('original_width'), result.get('original_height'))
                        x = int(rect['x'] * image_size[0] / 100)
                        y = int(rect['y'] * image_size[1] / 100)
                        width = int(rect['width'] * image_size[0] / 100)
                        height = int(rect['height'] * image_size[1] / 100)

                        # Border color
                        color = self.ids_and_colors['rectanglelabels'].get(label, {}).get('color', "#FF0000")

                        # Draw the rectangle with border thickness
                        for i in range(border_thickness):
                            draw.rectangle([
                                (x - i, y - i), 
                                (x + width + i, y + height + i)
                            ], outline=color)

            output_path = output_dir / f"{image_name.split('.')[0]}_rectangles.png"
            original_image.save(output_path)

        print("✅ Rectangle masks exported successfully!")